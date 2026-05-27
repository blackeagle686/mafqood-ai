# Mafqood AI: New AI Features & Capabilities

This document outlines the latest AI services and processing pipelines added to the Mafqood system to enhance the search and identification of missing persons.

## 🧬 DNA Kinship & Identity Matching
**Service Module:** `dna_search_service.py`

The newly introduced `DNASearchService` provides robust DNA STR (Short Tandem Repeat) profile analysis. It acts as a digital forensics engine capable of identifying individuals and mapping biological relationships.
- **Profile Validation:** Ensures the structural integrity of incoming DNA profiles, verifying loci and alleles including standard markers (e.g., CODIS core loci) and the AMEL sex determination marker.
- **Direct Identity Evaluation:** Compares profiles for an exact 100% identity match across overlapping loci.
- **Parent-Child Kinship Analysis:** Evaluates parent-child compatibility based on strict Mendelian inheritance rules (the child must inherit exactly one allele from each biological parent at every locus).
- **Sibling Kinship Estimation:** Evaluates sibling relationships using Identity by State (IBS) scoring (siblings can share 0, 1, or 2 alleles at any given locus).
- **Profile Searching:** Searches and ranks query profiles against target databases based on the chosen search logic (direct, parent-child, or sibling) and a required minimum locus overlap.

## ⏳ Neural Age Progression
**Service Module:** `age_progression_service.py`

The `AgeProgressionGAN` module generates age-progressed versions of missing children's faces, simulating how they might look years later.
- **CPU-Optimized GAN/Autoencoders:** Utilizes pre-trained lightweight models compiled to ONNX format with graph optimization and threaded execution for highly efficient CPU inference without requiring expensive GPUs.
- **Multi-Year Progression:** Can generate multiple progressed images simultaneously for various specified age jumps (e.g., +5, +10, +15 years).
- **FRAN & Standard GAN Support:** Supports multiple neural architectures including standard 3-channel GANs and 5-channel FRAN (Face Research Aging Network) residual map models.
- **Fallback Simulation Engine:** Includes an optimized algorithmic fallback that applies noise and blurring to simulate aging if the primary AI models are missing.

## 🧩 Autonomous Face Clustering
**Service Module:** `clustering_service.py`

The `ClusteringAgent` acts as an intelligent background monitor that autonomously groups similar faces and cases together within the database.
- **DBSCAN Unsupervised Clustering:** Employs the DBSCAN algorithm to group matching individuals by analyzing the Cosine Distance between normalized facial embeddings.
- **Dynamic System Monitoring:** Evaluates the database state dynamically to determine when a re-clustering operation is necessary based on the volume of new cases.
- **Vector Database Integration:** Fetches vectors from the database, processes them, and seamlessly updates the records' metadata with appropriate cluster assignments to group related cases.

## 🎞️ Intelligent Video Processing Pipeline
**Service Module:** `video_pipeline.py`

The `VideoProcessor` service extends the system's face recognition capabilities from static images to continuous video sources (CCTV, user uploads, etc.).
- **Optimized Frame Sampling:** Processes video streams efficiently by sampling every Nth frame (configurable sampling rate), drastically reducing computational load while maintaining accuracy.
- **Memory-Efficient Analysis:** Temporarily writes frames to disk during inference to avoid memory bloat and CPU thrashing on large video files, utilizing immediate post-process cleanup.
- **Integrated Face Search:** Leverages the core `FaceSearchService` to analyze the sampled frames and returns timestamped matches of recognized missing individuals.
