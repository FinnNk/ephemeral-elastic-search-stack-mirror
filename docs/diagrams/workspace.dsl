workspace "Ephemeral search relevance lab" "Local reference topology • September 2026 • Azure placement proposed" {
    !impliedRelationships true
    model {
        engineer = person "Lab user" "Changes search code, models and data."
        operator = person "Platform engineer" "Operates the lab and tests capacity."

        delivery = softwareSystem "Source and build platform" "Git, pull requests, builds and images. Gitea locally; GitHub Enterprise later." {
            gitea = container "Gitea" "Stores source, desired state and historical images." "Gitea; Git / OCI" {
                tags "Platform"
            }
            runner = container "Build runner" "Tests exact source, publishes a release and checks selected variants against signed evidence and a build receipt." "Actions / shared shell and Python" {
                tags "Platform"
            }
            nexus = container "Nexus" "Retains private images, immutable build receipts, release bundles and source-bound evaluation evidence." "Nexus Community Edition" {
                tags "Store"
            }
            nexusdb = container "Nexus metadata" "Retains artifact metadata and repository configuration." "PostgreSQL 17" {
                tags "Store"
            }
            enterprise = container "GitHub Enterprise Server" "Hosts source, pull requests and build events after migration." "GitHub Enterprise Server" {
                tags "Future"
            }
            registry = container "Azure Container Registry" "Retains tested image digests for AKS." "OCI registry" {
                tags "Future"
            }
        }
        platform = softwareSystem "Deployment platform" "Runs workloads and authenticates lab users." {
            localDns = container "Local lab DNS" "Resolves fixed platform and wildcard preview names to loopback." "CoreDNS / UDP and TCP" {
                tags "Platform"
            }
            previewRouter = container "Preview route reconciler" "Manages namespace-owned routes for labelled search services." "Python / Kubernetes API" {
                tags "Platform"
            }
            edge = container "HTTPS ingress" "Routes platform and preview requests over TLS." "Traefik locally / ingress on AKS" {
                tags "Platform"
            }
            identity = container "Keycloak" "Authenticates named lab users and issues group claims." "OIDC / Keycloak 26.6.4" {
                tags "Platform"
            }
            identitydb = container "Identity database" "Retains realm, clients, users and sessions." "PostgreSQL 17.6" {
                tags "Store"
            }
            headlamp = container "Headlamp" "Inspects cluster workloads using the signed-in user identity." "Headlamp / Kubernetes API" {
                tags "Platform"
            }
            argo = container "Argo CD" "Reconciles environment resources." "Argo CD / Helm" {
                tags "Platform"
            }
            kube = container "Kubernetes API" "Manages workloads and reports readiness." "Kubernetes" {
                tags "Platform"
            }
            eck = container "ECK operator" "Manages shared and version-test clusters." "Elastic Cloud on Kubernetes" {
                tags "Platform"
            }
            eso = container "External Secrets Operator" "Refreshes retained credentials into Kubernetes Secrets." "ESO / SecretStore / ExternalSecret" {
                tags "Platform"
            }
        }
        inputProduction = softwareSystem "Input production" "Publishes versioned catalogue, query, judgement and traffic artifacts." {
            producer = container "Input producer Job" "Validates and publishes independent frozen inputs." "Finite Kubernetes Job / pinned OCI image" {
                tags "Job"
            }
        }
        assessment = softwareSystem "Offline evaluation" "Scores named Search API variants under one pinned specification and judgement set." {
            offline = container "Offline evaluator" "Scores every named variant against the selected baseline and publishes a pinned report." "Pinned OCI image / finite invocation" {
                tags "Job"
            }
        }
        judgementSupply = softwareSystem "Judgement supply" "Returns stored published labels and attempts to resolve gaps." {
            judgementApi = container "Judgement API" "Checks frozen query/product records; stores labels and inference attempts." "Python HTTP API / SQLite" {
                tags "Platform"
            }
            kserve = container "KServe predictor" "Serves a numbered MLflow model version and returns its identity." "KServe Standard / Python predictor" {
                tags "Platform"
            }
            mlflow = container "MLflow registry" "Records registered model versions and artefact locations." "MLflow / PostgreSQL" {
                tags "Platform"
            }
            modelStore = container "Model artefact store" "Retains registered model files separately from index snapshots." "SeaweedFS S3 locally / Azure object store proposed" {
                tags "Store"
            }
        }
        observability = softwareSystem "Lab observability" "Collects lab signals and supports operational investigation." {
            gateway = container "OTel gateway" "Receives OTLP, redacts attributes and forwards bounded batches." "OpenTelemetry Collector Contrib" {
                tags "Platform"
            }
            logagent = container "Log agent" "Reads selected Kubernetes stdout events once per node." "OpenTelemetry Collector Contrib / DaemonSet" {
                tags "Platform"
            }
            ingester = container "SigNoz collector" "Ingests traces, metrics and logs for SigNoz." "SigNoz OTel Collector" {
                tags "Platform"
            }
            signoz = container "SigNoz" "Shows SLO activity, traces, metrics and logs." "SigNoz Community" {
                tags "Platform"
            }
            telemetrydb = container "Telemetry store" "Retains bounded operational signals." "ClickHouse / persistent volume" {
                tags "Store"
            }
        }
        lab = softwareSystem "Search relevance lab" "Creates environments; checks relevance, results and performance." {
            ui = container "Lab web UI" "Creates environments and displays comparisons." "HTML / JavaScript in control Pod"
            controlAuth = container "Control sign-in proxy" "Authenticates browser users and forwards signed identities." "OAuth2 Proxy 7.15.5" {
                tags "Platform"
            }
            api = container "Lab API" "Manages experiments, leases and comparisons." "Python HTTP API in control Pod"
            coordinator = container "Delivery coordinator" "Validates promotion PRs and verifies deployments." "Python worker in control Pod / provider adapter"
            metadata = container "Lab metadata" "Retains environment records, leases and report links." "SQLite on control PVC; shared store for AKS" {
                tags "Store"
            }
            search = container "Search API" "Understands queries, retrieves products and reranks results." "HTTP API / pinned OCI image" {
                tags "Ephemeral"
            }
            evaluation = container "Observation capture job" "Queries every frozen variant and retains ordered public API results." "Kubernetes Job / public Search API adapter" {
                tags "Job"
            }
            performance = container "Gatling load job" "Measures API latency, throughput and errors under pinned load." "Kubernetes Job / Gatling OSS Java SDK" {
                tags "Job"
            }
            notebook = container "Exploratory notebook job" "Runs a selected notebook on a retained comparison report." "Kubernetes Job / Papermill" {
                tags "Job"
            }
            indexing = container "Index build job" "Builds a shared or dedicated index from a pinned catalogue recipe." "Kubernetes Job / Elasticsearch bulk API" {
                tags "Job"
            }
            generator = container "Workload compiler" "Compiles frozen traffic traces into load profiles." "Versioned batch job" {
                tags "Job"
            }
            artifacts = container "Azure Blob Storage" "Retains frozen data, index recipes, workloads, query assets and reports." "Blob API" {
                tags "Store"
            }
            keyvault = container "Azure Key Vault" "Retains lab service credentials for ESO." "Secrets API" {
                tags "Store"
            }
            snapshots = container "Index snapshot repository" "Retains index snapshots after environment deletion." "SeaweedFS S3 locally / Azure Blob proposed" {
                tags "Store"
            }
            elastic = container "Shared search engine" "Serves shared frozen indices and dedicated experiment indices." "Self-managed Elasticsearch" {
                tags "Store"
            }
            expiry = container "Lease cleanup worker" "Reconciles expired leases and partial deletion." "Python worker in control Pod" {
                tags "Job"
            }
        }
        engineer -> lab "Creates and compares experiments"
        engineer -> localDns "Resolves local lab names" "DNS"
        previewRouter -> kube "Discovers search services; reconciles scoped routes" "Kubernetes API"
        edge -> search "Routes preview search pages" "HTTP inside cluster"
        engineer -> inputProduction "Selects source inputs"
        inputProduction -> lab "Publishes frozen source inputs" "Manifest and Blob API"
        lab -> assessment "Submits retained observations for scoring" "Artifact references"
        assessment -> judgementSupply "Resolves pooled gaps from every variant before scoring" "Versioned JSON API"
        operator -> lab "Validates lifecycle and isolation"
        engineer -> delivery "Pushes code and opens pull requests" "Git / HTTPS"
        operator -> platform "Operates cluster and reconciliation" "HTTPS"
        engineer -> edge "Opens lab web services" "HTTPS"
        edge -> gitea "Routes source and review pages" "HTTP in cluster"
        edge -> argo "Routes deployment UI" "HTTP in cluster"
        edge -> ui "Routes lab UI and API" "HTTP in cluster"
        edge -> signoz "Routes observability UI" "HTTP in cluster"
        operator -> headlamp "Inspects and manages lab workloads" "HTTPS / OIDC"
        engineer -> headlamp "Inspects lab workloads" "HTTPS / OIDC"
        engineer -> argo "Reviews deployments" "HTTPS / OIDC"
        engineer -> identity "Signs in" "HTTPS"
        headlamp -> identity "Authenticates users" "OIDC / verified TLS"
        argo -> identity "Authenticates users" "OIDC / verified TLS"
        controlAuth -> identity "Authenticates users" "OIDC / verified TLS"
        engineer -> controlAuth "Opens control UI" "HTTPS / OIDC"
        controlAuth -> api "Forwards requests and signed ID tokens" "HTTP in cluster"
        api -> identity "Verifies issuer and signing keys" "OIDC discovery / verified TLS"
        gitea -> identity "Authenticates linked accounts; retains Gitea roles" "OIDC / verified TLS"
        kube -> identity "Verifies issuer and signing keys" "OIDC discovery / verified TLS"
        identity -> identitydb "Retains identity state" "SQL"
        edge -> identity "Routes sign-in" "HTTP in cluster"
        edge -> headlamp "Routes cluster UI" "HTTP in cluster"
        headlamp -> kube "Uses the signed-in user permissions" "Kubernetes API / TLS"
        edge -> nexus "Routes artifact UI" "HTTP in cluster"
        engineer -> observability "Investigates lab operations" "Browser"
        operator -> observability "Checks telemetry coverage and capacity" "Browser"
        lab -> delivery "Resolves revisions and digests; publishes status" "Git / HTTPS"
        lab -> platform "Supplies desired state and observes readiness" "Git / HTTPS"
        delivery -> lab "Provides source revisions and build records" "Git / REST"
        engineer -> ui "Manages experiments" "HTTPS"
        ui -> api "Creates experiments, searches and compares" "JSON / HTTPS"
        api -> metadata "Records fingerprints, leases and state" "SQL"
        api -> artifacts "Pins and reads frozen manifests, index recipes and reports" "Azure Blob API"
        api -> search "Proxies interactive search" "JSON / HTTP"
        api -> argo "Publishes environment desired state" "Desired-state Git"
        api -> kube "Observes readiness and job completion" "Kubernetes API"
        api -> gitea "Polls labelled PR revisions, resolves exact builds and posts check status" "Gitea REST"
        api -> enterprise "Future provider adapter" "Git / REST" {
            tags "Future"
        }
        api -> registry "Resolves candidate image digests after migration" "OCI API" {
            tags "Future"
        }
        expiry -> metadata "Finds expired leases and records cleanup" "SQLite"
        gitea -> runner "Offers a build for a pinned commit" "Actions protocol"
        runner -> gitea "Fetches source and pushes tested images" "Git / HTTPS; OCI / HTTP"
        runner -> nexus "Publishes image, bundle and release receipt" "OCI / REST"
        nexus -> runner "Supplies signed variant evidence and its pinned source build receipt" "REST"
        nexus -> nexusdb "Stores repository metadata" "PostgreSQL"
        engineer -> gitea "Reviews source and promotion PRs" "Browser / Git"
        coordinator -> gitea "Proposes and validates exact promotion revisions" "Git / REST over HTTPS"
        coordinator -> nexus "Verifies release and bundle hashes" "REST"
        coordinator -> artifacts "Retains frozen check and deployment evidence" "Blob API"
        coordinator -> evaluation "Runs full result and relevance checks" "Kubernetes Job"
        coordinator -> performance "Runs paired API load checks" "Kubernetes Job"
        coordinator -> argo "Observes deployment health and revision" "Kubernetes API"
        coordinator -> search "Verifies the declared API deployment" "Public search API"
        argo -> gitea "Reads approved deployment state" "Git"
        kube -> nexus "Pulls private images by digest" "OCI"
        runner -> registry "Pushes tested image after migration" "OCI / HTTPS" {
            tags "Future"
        }
        runner -> api "Future verified build callback" "Authenticated callback" {
            tags "Future"
        }
        gitea -> api "Future source and PR events" "Signed webhook" {
            tags "Future"
        }
        enterprise -> api "Future source and PR events" "Signed webhook" {
            tags "Future"
        }
        argo -> kube "Applies desired workloads and pruning" "Kubernetes API"
        eck -> kube "Reconciles Elasticsearch resources" "Kubernetes API"
        eso -> keyvault "Reads retained service credentials" "Key Vault API"
        eso -> kube "Creates and refreshes namespace Secrets" "Kubernetes API"
        eck -> elastic "Manages cluster configuration" "Kubernetes resources"
        kube -> search "Runs pinned environment deployment" "OCI image"
        kube -> registry "Pulls pinned images on AKS" "OCI / HTTPS" {
            tags "Future"
        }
        kube -> evaluation "Runs comparison" "Job"
        kube -> performance "Runs scheduled load test" "Job"
        kube -> notebook "Runs optional report analysis" "Job"
        kube -> indexing "Runs mapping build" "Job"
        search -> elastic "Retrieves products with scoped credentials" "Elasticsearch REST"
        search -> gateway "Exports request traces and unsampled SLI counts" "OTLP/HTTP"
        api -> gateway "Exports control operation signals" "OTLP/HTTP"
        expiry -> gateway "Exports lease operation signals" "OTLP/HTTP"
        coordinator -> gateway "Exports delivery verification signals" "OTLP/HTTP"
        logagent -> gateway "Forwards selected structured stdout events" "OTLP/gRPC"
        gateway -> ingester "Forwards bounded signals" "OTLP/gRPC"
        ingester -> telemetrydb "Stores lab telemetry" "ClickHouse protocol"
        signoz -> telemetrydb "Queries operational signals" "ClickHouse protocol"
        engineer -> signoz "Follows operational evidence" "Browser"
        search -> artifacts "Loads pinned query assets" "Azure Blob API"
        evaluation -> search "Queries two or more named variants across frozen APIs" "Public search API"
        evaluation -> artifacts "Reads inputs and load reports; saves verdicts" "Azure Blob API"
        producer -> artifacts "Publishes immutable source inputs and manifests" "Blob API"
        offline -> artifacts "Reads observations and judgements; retains reports" "Blob API"
        offline -> judgementApi "Resolves missing pooled query-product pairs" "JSON / HTTP"
        offline -> gateway "Exports optional evaluation trace and input shift" "OTLP/HTTP"
        judgementApi -> artifacts "Loads pinned ESCI catalogue, queries and labels" "Azure Blob API"
        judgementApi -> kserve "Requests labels for missing pairs" "KServe V1 inference API"
        judgementApi -> gateway "Exports resolution spans and outcome counts" "OTLP/HTTP"
        kserve -> gateway "Exports inference spans, latency and outcomes" "OTLP/HTTP"
        kserve -> mlflow "Downloads exact registered model version at startup" "MLflow registry API"
        mlflow -> modelStore "Stores model artefacts" "S3 locally"
        performance -> search "Loads one pinned API at a time" "Public search API / HTTP"
        performance -> artifacts "Reads compiled workload; saves reports" "Azure Blob API"
        api -> notebook "Submits selected notebook after report retention" "Kubernetes Job"
        notebook -> artifacts "Reads frozen comparison report" "Read-only Blob URL"
        notebook -> api "Returns executed notebook for retention" "Job output"
        indexing -> artifacts "Reads immutable catalogue" "Azure Blob API"
        indexing -> elastic "Builds a recipe-marked frozen index" "Bulk REST API"
        elastic -> snapshots "Saves and restores recipe-matched index copies" "S3 locally / Azure Blob proposed"
        generator -> artifacts "Reads inputs; freezes data, traces and workloads" "Azure Blob API"
        api -> elastic "Verifies, clones or restores frozen indices; manages scoped access and cleanup" "Elasticsearch REST"

        deploymentEnvironment "Local lab" {
            deploymentNode "Developer machine" "Windows x64; Apple silicon support to validate" "Local host" {
                deploymentNode "Snapshot storage" "Docker volume survives Elasticsearch Pod and data-PVC replacement" "Host Docker service" {
                    containerInstance snapshots
                    containerInstance modelStore
                }
                deploymentNode "Release storage" "Separate persistent volumes; loopback administration" "Host Docker services" {
                    containerInstance nexus
                    containerInstance nexusdb
                }
                deploymentNode "Local Kubernetes" "Three-node k3d cluster, including a dedicated observability worker" "Kubernetes" {
                    deploymentNode "HTTPS ingress" "One loopback TLS port for retained web services" "lab-ingress namespace / Traefik" {
                        containerInstance edge
                        containerInstance localDns
                        containerInstance previewRouter
                    }
                    deploymentNode "Local control plane" "Cluster control services" "Kubernetes control plane" {
                        containerInstance kube
                    }
                    deploymentNode "Persistent platform namespace" "Survives environment deletion" "Namespace" {
                        containerInstance gitea
                        containerInstance runner
                        containerInstance argo
                        containerInstance eck
                    }
                    deploymentNode "Secret synchronisation" "ESO runs outside experiment namespaces" "lab-secrets namespace" {
                        containerInstance eso
                    }
                    deploymentNode "Lab control namespace" "Control workers, sign-in proxy and retained SQLite/Git state" "Namespace / persistent volume" {
                        containerInstance ui
                        containerInstance api
                        containerInstance controlAuth
                        containerInstance metadata
                        containerInstance expiry
                        containerInstance coordinator
                    }
                    deploymentNode "Azure service emulation" "Retained Blob Storage and Key Vault data" "Floci / namespace / persistent volume" {
                        containerInstance artifacts
                        containerInstance keyvault
                    }
                    deploymentNode "Observability worker" "Pinned SigNoz backend and retained telemetry" "lab-observability / 12 GiB worker" {
                        containerInstance gateway
                        containerInstance ingester
                        containerInstance signoz
                        containerInstance telemetrydb
                    }
                    deploymentNode "Cluster UI" "Named user sign-in" "lab-headlamp namespace" {
                        containerInstance headlamp
                    }
                    deploymentNode "Log collection" "One scoped agent on each node" "lab-observability / DaemonSet" {
                        containerInstance logagent
                    }
                    deploymentNode "Shared search namespace" "One shared engine; scoped index credentials" "Namespace / persistent volume" {
                        containerInstance elastic
                    }
                    deploymentNode "Judgement and model services" "CPU APIs, registry and bootstrap predictor" "lab-models namespace / persistent volumes" {
                        containerInstance judgementApi
                        containerInstance kserve
                        containerInstance mlflow
                    }
                    deploymentNode "Identity services" "Persistent users, clients and sessions on the CPU worker" "lab-identity namespace / PVC" {
                        containerInstance identity
                        containerInstance identitydb
                    }
                    deploymentNode "Optional GPU worker" "CUDA predictor after qualification; omitted on Apple silicon" "NVIDIA / separate k3s agent / lab-models" {
                        containerInstance kserve
                    }
                    deploymentNode "Experiment namespaces" "2–3 locally; one API deployment per namespace" "Namespaces / quotas / policies" {
                        containerInstance search
                    }
                    deploymentNode "Indexing namespace" "Temporary index Jobs and credentials" "Namespace / Job" {
                        containerInstance indexing
                    }
                    deploymentNode "Comparison jobs" "Bounded jobs spanning baseline and candidate" "Namespace / quotas" {
                        containerInstance evaluation
                        containerInstance performance
                    }
                    deploymentNode "Exploratory notebooks" "Optional finite jobs over retained reports" "lab-notebooks namespace" {
                        containerInstance notebook
                    }
                    deploymentNode "Independent input and scoring jobs" "Finite producer and evaluator" "lab-data and lab-offline-evaluation / Jobs" {
                        containerInstance producer
                        containerInstance offline
                    }
                }
            }
        }
        deploymentEnvironment "Azure target" {
            deploymentNode "Organisation delivery services" "Migration destination; hosting details to be agreed" "Enterprise services" {
                containerInstance enterprise
                containerInstance runner
                containerInstance nexus
                containerInstance nexusdb
            }
            deploymentNode "Azure subscription" "Hosts lab workloads and retained artifacts" "Azure" {
                deploymentNode "Azure Blob Storage" "Frozen releases, reports and proposed snapshot container" "Azure managed service" {
                    containerInstance artifacts
                    containerInstance snapshots
                }
                deploymentNode "Azure Key Vault" "Retained service credentials; Workload Identity access to validate" "Azure managed service" {
                    containerInstance keyvault
                }
                deploymentNode "Azure Container Registry" "Optional image distribution; retain Nexus for releases" "Azure managed service" {
                    containerInstance registry
                }
                deploymentNode "AKS cluster" "Hosts 40+ environments; capacity to validate" "Azure Kubernetes Service" {
                    deploymentNode "Managed control plane" "AKS-managed cluster control services" "Kubernetes control plane" {
                        containerInstance kube
                    }
                    deploymentNode "Platform and lab services" "Persistent services; metadata topology remains open" "Namespaces" {
                        containerInstance edge
                        containerInstance argo
                        containerInstance eck
                        containerInstance eso
                        containerInstance ui
                        containerInstance api
                        containerInstance controlAuth
                        containerInstance metadata
                        containerInstance expiry
                        containerInstance coordinator
                        containerInstance gateway
                        containerInstance logagent
                        containerInstance judgementApi
                        containerInstance kserve
                        containerInstance mlflow
                    }
                    deploymentNode "Model artefacts" "Object storage option to validate" "Azure object store" {
                        containerInstance modelStore
                    }
                    deploymentNode "Shared Elasticsearch nodes" "Self-managed under ECK; contention measured separately" "Stateful workloads / persistent disks" {
                        containerInstance elastic
                    }
                    deploymentNode "Experiment worker nodes" "Separate namespaces; bound concurrent indexing" "Scalable node pool" {
                        containerInstance search
                        containerInstance indexing
                    }
                    deploymentNode "Comparison workers" "Reserved load-generator resources; lab-owned namespace" "Separate worker pool / quotas" {
                        containerInstance evaluation
                        containerInstance performance
                        containerInstance notebook
                    }
                    deploymentNode "Independent input and scoring jobs" "Separate artifact producers and evaluator" "Namespaces / jobs" {
                        containerInstance producer
                        containerInstance offline
                    }
                }
            }
        }
    }
    views {
        systemContext lab "01-context" {
            title "C4 System context — search relevance lab"
            include engineer operator lab delivery platform inputProduction assessment judgementSupply
            autolayout lr
        }
        container lab "02-control" {
            title "C4 Containers — environment control and delivery"
            include engineer ui api metadata expiry delivery platform search
            autolayout lr
        }
        container lab "03-evaluation" {
            title "C4 Containers — API capture, index and load checks"
            include generator artifacts indexing elastic snapshots search evaluation performance notebook judgementApi kserve mlflow modelStore
            autolayout lr
        }
        container delivery "18-delivery" {
            title "C4 Containers — immutable release delivery"
            include engineer gitea runner nexus coordinator argo kube search artifacts
            autolayout lr
        }
        container platform "07-preview" {
            title "C4 Containers — local DNS and preview access"
            include engineer localDns edge previewRouter kube search
            autolayout lr
        }
        container platform "09-identity" {
            title "C4 Containers — lab identity and permissions"
            include engineer identity identitydb headlamp argo kube eso keyvault gitea controlAuth api
            autolayout lr
        }
        dynamic lab "04-create" {
            title "C4 Dynamic — create a candidate from a labelled Gitea PR"
            gitea -> runner "Builds pinned source revision"
            runner -> gitea "Publishes tested OCI image digest"
            api -> gitea "Polls PR head and matching successful build"
            api -> argo "Publishes desired environment"
            argo -> kube "Reconciles declared resources"
            kube -> search "Starts pinned search API"
            search -> elastic "Verifies first correct search"
            autolayout lr
        }
        deployment * "Local lab" "05-local" {
            title "C4 Deployment — self-contained local lab"
            include *
            autolayout lr
        }
        deployment * "Azure target" "06-azure" {
            title "C4 Deployment — Azure target (proposed)"
            include *
            autolayout lr
        }
        styles {
            element "Element" {
                color #ffffff
                background #22577a
                stroke #163b55
                fontSize 24
            }
            element "Person" {
                shape Person
                background #16324f
            }
            element "Software System" {
                background #16324f
            }
            element "Container" {
                shape RoundedBox
            }
            element "Store" {
                shape Cylinder
                background #256d5d
            }
            element "Job" {
                background #6554a4
            }
            element "Platform" {
                background #556677
            }
            element "Ephemeral" {
                background #007e91
            }
            element "Future" {
                background #687482
                border Dashed
            }
            element "Deployment Node" {
                color #25364b
                background #f4f7fa
                stroke #b5c5d2
                fontSize 24
            }
            relationship "Relationship" {
                color #536879
                fontSize 20
                thickness 2
                routing Direct
                dashed false
            }
            relationship "Diagnostic" {
                color #ac6a18
                dashed true
            }
            relationship "Future" {
                dashed true
            }
        }
    }
}
