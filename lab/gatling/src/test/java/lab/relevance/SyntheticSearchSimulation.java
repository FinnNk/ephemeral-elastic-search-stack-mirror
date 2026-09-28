package lab.relevance;

import io.gatling.javaapi.core.OpenInjectionStep;
import io.gatling.javaapi.core.PopulationBuilder;
import io.gatling.javaapi.core.ScenarioBuilder;
import io.gatling.javaapi.core.Simulation;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.StandardOpenOption;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

import static io.gatling.javaapi.core.CoreDsl.*;
import static io.gatling.javaapi.http.HttpDsl.*;

/** One request per virtual user, with open arrivals compiled from a frozen synthetic trace. */
public class SyntheticSearchSimulation extends Simulation {
  private static final Path WORKLOAD = Path.of(System.getProperty("lab.workload", "/workload"));
  private static final Path ARRIVALS = Path.of(System.getProperty("lab.arrivals", "/results/arrivals.csv"));
  private static final String BASE_URL = System.getProperty("lab.baseUrl", "http://search.retail-baseline.svc.cluster.local:8080");
  private static final String PROFILE = System.getProperty("lab.profile", "probe");

  private static String trafficClass(String phase) {
    if (PROFILE.equals("probe") || PROFILE.equals("smoke")) return "probe";
    if (phase.equals("ramp")) return "warmup";
    if (phase.startsWith("stress")) return "stress";
    return phase;
  }

  private static synchronized void arrival(String phase, String queryId, String plannedMs) {
    try {
      Files.createDirectories(ARRIVALS.getParent());
      Files.writeString(ARRIVALS, System.currentTimeMillis() + "," + phase + "," + queryId + "," + plannedMs + "\n",
          StandardOpenOption.CREATE, StandardOpenOption.APPEND);
    } catch (IOException error) {
      throw new IllegalStateException("Cannot record actual arrival", error);
    }
  }

  public SyntheticSearchSimulation() throws IOException {
    Map<String, List<int[]>> phases = new LinkedHashMap<>();
    List<String> lines = Files.readAllLines(WORKLOAD.resolve("schedule.csv"));
    for (String line : lines.subList(1, lines.size())) {
      String[] fields = line.split(",", -1);
      phases.computeIfAbsent(fields[0], ignored -> new ArrayList<>())
          .add(new int[] {Integer.parseInt(fields[1]), Integer.parseInt(fields[2])});
    }
    List<PopulationBuilder> populations = new ArrayList<>();
    for (Map.Entry<String, List<int[]>> phase : phases.entrySet()) {
      String name = phase.getKey();
      ScenarioBuilder scenario = scenario(name)
          .feed(csv(WORKLOAD.resolve(name + ".csv").toString()).queue())
          .exec(session -> {
            arrival(name, session.getString("query_id"), session.getString("planned_ms"));
            return session;
          })
          .exec(http(name).get("/search")
              .header("X-Lab-Traffic-Class", trafficClass(name))
              .queryParam("q", "#{query}").queryParam("country", "GB").queryParam("currency", "GBP")
              .check(status().is(200), jsonPath("$.ids").exists()));
      List<OpenInjectionStep> steps = new ArrayList<>();
      int previous = 0;
      for (int[] bucket : phase.getValue()) {
        int gap = bucket[0] - previous;
        if (gap > 0) steps.add(nothingFor(gap));
        if (bucket[1] > 0) steps.add(constantUsersPerSec(bucket[1]).during(1));
        else steps.add(nothingFor(1));
        previous = bucket[0] + 1;
      }
      populations.add(scenario.injectOpen(steps.toArray(new OpenInjectionStep[0])));
    }
    setUp(populations.toArray(new PopulationBuilder[0]))
        .protocols(http.baseUrl(BASE_URL).acceptHeader("application/json"));
  }
}
