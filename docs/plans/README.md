# Delivery plan

The [batch roadmap](roadmap.md) tracks lab work and review state. The [million-product](million-product-scale.md), [concurrency](concurrency-isolation.md), [portability](portability-azure.md) and [native/cloud validation](native-cloud-validation.md) plans record intent, constraints and acceptance checks. Each batch is committed on a branch and submitted as a pull request. Later pull requests may target the preceding branch so work can continue while the stack awaits review; merge them in order.

The [reference CI/CD plan](reference-ci-cd.md) inserts batches 7f–7h: [Nexus](nexus-artifacts.md), [portable CI](portable-ci.md) and [promotion/deployment](promotion-deployment.md). Their implementation is ready for review.

The next local batches are [7i: Kubernetes control services](kubernetes-control-services.md) and [7j: independent data/evaluation contracts](independent-data-evaluation-contracts.md). Both include intent, constraints, work, acceptance criteria and source references. The [topology and contract assessment](local-reference-boundaries.md) distinguishes the remaining structural checks from deliberate laptop simplifications. [Batch 8](native-cloud-validation.md) follows and requires external hardware/tenant access.

The [prototype design](../prototype-design.md) owns the architecture and provisional quantitative targets. These plans organise delivery without replacing that design.
