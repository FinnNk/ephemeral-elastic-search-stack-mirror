workspace "Ephemeral search relevance lab" "Proposed architecture • September 2026 • research choices remain open" {
    !impliedRelationships true
    model {
        engineer = person "Lab user" "Changes search code, models and data."
        operator = person "Platform engineer" "Operates the lab and tests capacity."

        delivery = softwareSystem "Source and build platform" "Git, pull requests, builds and images. Gitea locally; GitHub Enterprise later." {
            gitea = container "Gitea" "Stores source, desired state and OCI images." "Gitea; Git / OCI" {
                tags "Platform"
            }
            runner = container "Build runner" "Tests source and publishes a pinned image." "Gitea Actions locally; target runner TBC" {
                tags "Platform"
            }
            enterprise = container "GitHub Enterprise Server" "Hosts source, pull requests and build events after migration." "GitHub Enterprise Server" {
                tags "Future"
            }
            registry = container "Azure Container Registry" "Retains tested image digests for AKS." "OCI registry" {
                tags "Future"
            }
        }
        platform = softwareSystem "Deployment platform" "Runs workloads through Argo CD, Kubernetes and ECK." {
            argo = container "Argo CD" "Reconciles environment resources." "Argo CD / Helm" {
                tags "Platform"
            }
            kube = container "Kubernetes API" "Manages workloads and reports readiness." "Kubernetes" {
                tags "Platform"
            }
            eck = container "ECK operator" "Manages shared and version-test clusters." "Elastic Cloud on Kubernetes" {
                tags "Platform"
            }
        }
        lab = softwareSystem "Search relevance lab" "Creates environments; checks relevance, results and performance." {
            ui = container "Lab web UI" "Creates environments and displays comparisons." "Host-served HTML / JavaScript locally"
            api = container "Lab API" "Manages experiments, leases and comparisons." "Python HTTP API locally"
            metadata = container "Lab metadata" "Retains environment records, leases and report links." "SQLite locally; shared store for AKS" {
                tags "Store"
            }
            search = container "Search API" "Understands queries, retrieves products and reranks results." "HTTP API / pinned OCI image" {
                tags "Ephemeral"
            }
            evaluation = container "Evaluation job" "Scores relevance, checks result changes and compares performance reports." "Kubernetes Job / metrics and comparison libraries" {
                tags "Job"
            }
            performance = container "Gatling load job" "Measures API latency, throughput and errors under pinned load." "Kubernetes Job / Gatling OSS Java SDK" {
                tags "Job"
            }
            indexing = container "Index build job" "Rebuilds a dedicated index from its pinned recipe and frozen products." "Kubernetes Job / Elasticsearch bulk API" {
                tags "Job"
            }
            generator = container "Dataset and workload generator" "Generates synthetic data and traces; compiles load profiles." "Versioned batch job" {
                tags "Job"
            }
            artifacts = container "Artifact store" "Retains frozen data, index recipes, workloads, query assets and reports." "Floci AZ locally / Azure Blob Storage later" {
                tags "Store"
            }
            elastic = container "Shared search engine" "Serves shared frozen indices and dedicated experiment indices." "Self-managed Elasticsearch" {
                tags "Store"
            }
            expiry = container "Lease cleanup job" "Reconciles expired leases and partial deletion." "Host process locally; Kubernetes CronJob target" {
                tags "Job"
            }
        }
        engineer -> lab "Creates and compares experiments"
        operator -> lab "Validates lifecycle and isolation"
        engineer -> delivery "Pushes code and opens pull requests" "Git / HTTPS"
        operator -> platform "Operates cluster and reconciliation" "HTTPS"
        lab -> delivery "Resolves revisions and digests; publishes status" "Git / HTTPS"
        lab -> platform "Supplies desired state and observes readiness" "Git / HTTPS"
        delivery -> lab "Notifies candidate build completion" "Signed webhook"
        engineer -> ui "Manages experiments" "HTTPS"
        ui -> api "Creates experiments, searches and compares" "JSON / HTTPS"
        api -> metadata "Records fingerprints, leases and state" "SQL"
        api -> artifacts "Pins and reads frozen manifests, index recipes and reports" "Azure Blob API"
        api -> search "Proxies interactive search" "JSON / HTTP"
        api -> argo "Publishes environment and job desired state" "Git files or plugin; TBC"
        api -> kube "Observes readiness and job completion" "Kubernetes API"
        api -> gitea "Resolves source, images and PR status" "Git / REST"
        api -> enterprise "Future provider adapter" "Git / REST" {
            tags "Future"
        }
        api -> registry "Resolves candidate image digests after migration" "OCI API" {
            tags "Future"
        }
        expiry -> metadata "Finds expired leases and records cleanup" "SQL locally; API contract on AKS"
        gitea -> runner "Offers a build for a pinned commit" "Actions protocol"
        runner -> gitea "Pushes tested image and digest" "OCI / HTTPS"
        runner -> registry "Pushes tested image after migration" "OCI / HTTPS" {
            tags "Future"
        }
        runner -> api "Reports verified build digest" "Authenticated callback"
        gitea -> api "Sends source and PR events" "Signed webhook"
        enterprise -> api "Future source and PR events" "Signed webhook" {
            tags "Future"
        }
        argo -> kube "Applies desired workloads and pruning" "Kubernetes API"
        eck -> kube "Reconciles Elasticsearch resources" "Kubernetes API"
        eck -> elastic "Manages cluster configuration" "Kubernetes resources"
        kube -> search "Runs pinned environment deployment" "OCI image"
        kube -> registry "Pulls pinned images on AKS" "OCI / HTTPS" {
            tags "Future"
        }
        kube -> evaluation "Runs comparison" "Job"
        kube -> performance "Runs scheduled load test" "Job"
        kube -> indexing "Runs mapping build" "Job"
        search -> elastic "Retrieves products with scoped credentials" "Elasticsearch REST"
        search -> artifacts "Loads pinned query assets" "Azure Blob API"
        evaluation -> search "Queries baseline and candidate APIs" "Public search API"
        evaluation -> artifacts "Reads inputs and load reports; saves verdicts" "Azure Blob API"
        performance -> search "Loads one pinned API at a time" "Public search API / HTTP"
        performance -> artifacts "Reads compiled workload; saves reports" "Azure Blob API"
        evaluation -> elastic "Optional white-box diagnostics only" "_rank_eval / profile / explain" {
            tags "Diagnostic"
        }
        indexing -> artifacts "Reads immutable catalogue" "Azure Blob API"
        indexing -> elastic "Creates a dedicated index" "Bulk REST API"
        generator -> artifacts "Reads inputs; freezes data, traces and workloads" "Azure Blob API"
        api -> elastic "Verifies, clones or restores frozen indices; manages scoped access and cleanup" "Elasticsearch REST"

        deploymentEnvironment "Local lab" {
            deploymentNode "Developer machine" "Windows x64; Apple silicon support to validate" "Local host" {
                deploymentNode "Local control process" "Loopback UI/API and SQLite state" "Host process" {
                    containerInstance ui
                    containerInstance api
                    containerInstance metadata
                    containerInstance expiry
                }
                deploymentNode "Local Kubernetes" "Measured two-node k3d cluster" "Kubernetes" {
                    deploymentNode "Local control plane" "Cluster control services" "Kubernetes control plane" {
                        containerInstance kube
                    }
                    deploymentNode "Persistent platform namespace" "Survives environment deletion" "Namespace" {
                        containerInstance gitea
                        containerInstance runner
                        containerInstance argo
                        containerInstance eck
                    }
                    deploymentNode "Persistent lab services" "Floci survives environment deletion" "Namespace / persistent volume" {
                        containerInstance artifacts
                    }
                    deploymentNode "Shared search namespace" "One shared engine; scoped index credentials" "Namespace / persistent volume" {
                        containerInstance elastic
                    }
                    deploymentNode "Experiment namespaces" "2–3 locally; one API deployment per namespace" "Namespaces / quotas / policies" {
                        containerInstance search
                        containerInstance indexing
                    }
                    deploymentNode "Comparison jobs" "Bounded jobs spanning baseline and candidate" "Namespace / quotas" {
                        containerInstance evaluation
                        containerInstance performance
                    }
                }
            }
        }
        deploymentEnvironment "Azure target" {
            deploymentNode "Organisation delivery services" "Migration destination; hosting details to be agreed" "Enterprise services" {
                containerInstance enterprise
                containerInstance runner
            }
            deploymentNode "Azure subscription" "Hosts lab workloads and retained artifacts" "Azure" {
                deploymentNode "Azure Blob Storage" "Frozen releases and reports" "Azure managed service" {
                    containerInstance artifacts
                }
                deploymentNode "Azure Container Registry" "Pinned multi-architecture API images" "Azure managed service" {
                    containerInstance registry
                }
                deploymentNode "AKS cluster" "Hosts 40+ environments; capacity to validate" "Azure Kubernetes Service" {
                    deploymentNode "Managed control plane" "AKS-managed cluster control services" "Kubernetes control plane" {
                        containerInstance kube
                    }
                    deploymentNode "Platform and lab services" "Persistent services; metadata topology remains open" "Namespaces" {
                        containerInstance argo
                        containerInstance eck
                        containerInstance ui
                        containerInstance api
                        containerInstance metadata
                        containerInstance expiry
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
                    }
                }
            }
        }
    }
    views {
        systemContext lab "01-context" {
            title "C4 System context — proposed search relevance lab"
            include engineer operator lab delivery platform
            autolayout lr
        }
        container lab "02-control" {
            title "C4 Containers — environment control and delivery"
            include engineer ui api metadata expiry delivery platform search
            autolayout lr
        }
        container lab "03-evaluation" {
            title "C4 Containers — frozen data and end-to-end evaluation"
            include generator artifacts indexing elastic search evaluation performance
            autolayout lr
        }
        dynamic lab "04-create" {
            title "C4 Dynamic — create a candidate from a Gitea change"
            gitea -> runner "Builds pinned source revision"
            runner -> gitea "Publishes tested OCI image digest"
            runner -> api "Reports verified revision and digest"
            api -> argo "Publishes desired environment"
            argo -> kube "Reconciles declared resources"
            kube -> search "Starts pinned search API"
            search -> elastic "Verifies first correct search"
            autolayout lr
        }
        deployment * "Local lab" "05-local" {
            title "C4 Deployment — self-contained local lab (proposed)"
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
