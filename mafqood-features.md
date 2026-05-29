# Mafqood AI: Core AI Lab Services & Capabilities

This document outlines the AI services and processing pipelines within the Mafqood system designed to assist in searching and identifying missing persons.

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

## 👤 Face Search & Vector Database Service `[connected with .NET]`
**Service Module:** `face_search_service.py`

The `FaceSearchService` handles all core face search, database indexing, and real-time matching dispatch workflows.
- **Intelligence Score Layer:** Computes a weighted match score based on 70% face similarity, 20% temporal context (decay score), and 10% geospatial proximity.
- **Piecewise Distance Mapping:** Maps raw cosine distance outputs from the vector DB to human-friendly similarity percentages using a customized piecewise linear scale.
- **On-Insert Cross-Matching:** Automates duplicate detection and triggers cross-status alerts (missing/found) upon indexing new records.
- **.NET Integration Webhook:** Dispatches real-time webhook alerts formatted with .NET-compatible JSON payloads directly to the Mafqood host system upon finding high-confidence matches.
- **Batch & Background Jobs:** Supports batch search queries and runs an asynchronous background reconciliation loop to audit older cases for missed matches.

## 📷 Computer Vision & Face Detection Pipeline
**Service Module:** `cv_service.py`

The `FaceCVPipeline` and model loading system coordinates raw image pre-processing, face detection, and feature extraction.
- **Model Loader Singleton:** Efficiently loads and caches InsightFace detection and analysis models in memory to optimize GPU/CPU execution context and supports an offline dummy mode.
- **Hardware-Aware Image Enhancement:** Applies denoising, dynamic gamma correction for poor/uneven lighting, and unsharp masking to enhance facial features before passing images to detection models.
- **Preserved Embedding Space:** Performs face detection on enhanced frames, but extracts embeddings from original raw frames to guarantee coordinates and descriptors remain unaltered.
- **Resolution & Size Filtering:** Rejects bounding boxes below minimum dimension thresholds to ensure the system ignores distant or noisy face-like artifacts.

## 💬 Natural Language Processing & Text Safety
**Service Module:** `nlp_service.py`

The NLP and text processing utilities enforce communication safety and normalize textual queries/reports.
- **Arabic Text Normalization:** Cleans Arabic inputs by stripping diacritics and unifying variant character forms (e.g., standardizing Alef, Teh Marbuta, and Yeh symbols) to prevent duplicate names and search misses.
- **Hybrid Appropriateness Classification:** Utilizes a custom LLM classification model for advanced semantic/contextual toxicity detection.
- **Static Dictionary Fallback:** Automatically falls back to a normalized bad-words lookup dictionary to maintain safety screening even during model latency or offline modes.
