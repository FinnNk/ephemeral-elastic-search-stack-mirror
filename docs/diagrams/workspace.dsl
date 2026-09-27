workspace "Ephemeral search relevance lab" "Local reference topology • September 2026 • Azure placement proposed" {
    !impliedRelationships true
    model {
        engineer = person "Lab user" "Changes search code, models and data."
        operator = person "Platform engineer" "Operates the lab and tests capacity."

        delivery = softwareSystem "Source and build platform" "Git, pull requests, builds and images. Gitea locally; GitHub Enterprise later." {
            gitea = container "Gitea" "Stores source, desired state and historical images." "Gitea; Git / OCI" {
                tags "Platform"
            }
            runner = container "Build runner" "Tests exact source; publishes frozen releases." "Actions / shared shell and Python" {
                tags "Platform"
            }
            nexus = container "Nexus" "Retains private images and immutable release bundles." "Nexus Community Edition" {
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
        inputProduction = softwareSystem "Synthetic input production" "Publishes versioned catalogue, query, judgement and traffic artifacts." {
            producer = container "Input producer Job" "Validates and publishes independent synthetic inputs." "Finite Kubernetes Job / pinned OCI image" {
                tags "Job"
            }
        }
        assessment = softwareSystem "Offline evaluation" "Scores retained observations under a pinned specification and judgement set." {
            offline = container "Offline evaluator" "Validates input dependencies and publishes a complete report." "Pinned OCI image / finite invocation" {
                tags "Job"
            }
        }
        lab = softwareSystem "Search relevance lab" "Creates environments; checks relevance, results and performance." {
            ui = container "Lab web UI" "Creates environments and displays comparisons." "HTML / JavaScript in control Pod"
            api = container "Lab API" "Manages experiments, leases and comparisons." "Python HTTP API in control Pod"
            coordinator = container "Delivery coordinator" "Validates promotion PRs and verifies deployments." "Python worker in control Pod / provider adapter"
            metadata = container "Lab metadata" "Retains environment records, leases and report links." "SQLite on control PVC; shared store for AKS" {
                tags "Store"
            }
            search = container "Search API" "Understands queries, retrieves products and reranks results." "HTTP API / pinned OCI image" {
                tags "Ephemeral"
            }
            evaluation = container "Observation capture job" "Queries both APIs and retains ordered results and comparison scores." "Kubernetes Job / public Search API adapter" {
                tags "Job"
            }
            performance = container "Gatling load job" "Measures API latency, throughput and errors under pinned load." "Kubernetes Job / Gatling OSS Java SDK" {
                tags "Job"
            }
            indexing = container "Index build job" "Builds a shared or dedicated index from a pinned catalogue recipe." "Kubernetes Job / Elasticsearch bulk API" {
                tags "Job"
            }
            generator = container "Workload compiler" "Compiles frozen traffic traces into load profiles." "Versioned batch job" {
                tags "Job"
            }
            artifacts = container "Artifact store" "Retains frozen data, index recipes, workloads, query assets and reports." "Floci AZ locally / Azure Blob Storage later" {
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
        engineer -> inputProduction "Revises synthetic inputs"
        inputProduction -> lab "Publishes frozen synthetic inputs" "Manifest and Blob API"
        lab -> assessment "Submits retained observations for scoring" "Artifact references"
        operator -> lab "Validates lifecycle and isolation"
        engineer -> delivery "Pushes code and opens pull requests" "Git / HTTPS"
        operator -> platform "Operates cluster and reconciliation" "HTTPS"
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
        runner -> gitea "Pushes tested image and digest" "OCI / HTTPS"
        runner -> nexus "Publishes image, bundle and release receipt" "OCI / REST"
        nexus -> nexusdb "Stores repository metadata" "PostgreSQL"
        engineer -> gitea "Reviews source and promotion PRs" "Browser / Git"
        coordinator -> gitea "Proposes and validates exact promotion revisions" "Git / REST"
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
        producer -> artifacts "Publishes immutable synthetic inputs and manifests" "Blob API"
        offline -> artifacts "Reads observations and judgements; retains reports" "Blob API"
        performance -> search "Loads one pinned API at a time" "Public search API / HTTP"
        performance -> artifacts "Reads compiled workload; saves reports" "Azure Blob API"
        indexing -> artifacts "Reads immutable catalogue" "Azure Blob API"
        indexing -> elastic "Builds a recipe-marked frozen index" "Bulk REST API"
        elastic -> snapshots "Saves and restores recipe-matched index copies" "S3 locally / Azure Blob proposed"
        generator -> artifacts "Reads inputs; freezes data, traces and workloads" "Azure Blob API"
        api -> elastic "Verifies, clones or restores frozen indices; manages scoped access and cleanup" "Elasticsearch REST"

        deploymentEnvironment "Local lab" {
            deploymentNode "Developer machine" "Windows x64; Apple silicon support to validate" "Local host" {
                deploymentNode "Snapshot storage" "Docker volume survives Elasticsearch Pod and data-PVC replacement" "Host Docker service" {
                    containerInstance snapshots
                }
                deploymentNode "Release storage" "Separate persistent volumes; loopback administration" "Host Docker services" {
                    containerInstance nexus
                    containerInstance nexusdb
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
                    deploymentNode "Lab control namespace" "One active Pod and retained SQLite/Git state" "Namespace / persistent volume" {
                        containerInstance ui
                        containerInstance api
                        containerInstance metadata
                        containerInstance expiry
                        containerInstance coordinator
                    }
                    deploymentNode "Persistent lab services" "Floci survives environment deletion" "Namespace / persistent volume" {
                        containerInstance artifacts
                    }
                    deploymentNode "Shared search namespace" "One shared engine; scoped index credentials" "Namespace / persistent volume" {
                        containerInstance elastic
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
                deploymentNode "Azure Container Registry" "Optional image distribution; retain Nexus for releases" "Azure managed service" {
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
                        containerInstance coordinator
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
            include engineer operator lab delivery platform inputProduction assessment
            autolayout lr
        }
        container lab "02-control" {
            title "C4 Containers — environment control and delivery"
            include engineer ui api metadata expiry delivery platform search
            autolayout lr
        }
        container lab "03-evaluation" {
            title "C4 Containers — API capture, index and load checks"
            include generator artifacts indexing elastic snapshots search evaluation performance
            autolayout lr
        }
        container delivery "18-delivery" {
            title "C4 Containers — immutable release delivery"
            include engineer gitea runner nexus coordinator argo kube search artifacts
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
