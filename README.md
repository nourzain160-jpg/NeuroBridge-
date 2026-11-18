NeuroBridge

A Personalized Neural Rehabilitation System

NeuroBridge is a research and development project exploring personalized upper-limb rehabilitation through multimodal biosignal processing and machine learning.

The system focuses on elbow flexion and extension by investigating the integration of surface electromyography (sEMG), inertial measurement units (IMUs), and electroencephalography (EEG) for movement-related signal analysis.

The project also incorporates a cybersecurity and privacy framework designed to protect sensitive biosignal data throughout its processing, transmission, and storage.

Project Overview

NeuroBridge explores two multimodal processing approaches:

1. Model A: sEMG + IMU
2. Model B: EEG + sEMG + IMU

The project investigates how combining neural and muscular signals with movement measurements may support more personalized rehabilitation monitoring.

These approaches are research hypotheses and are not yet clinically validated.

System Architecture

The proposed system architecture includes:

1- sEMG Sensors: Capture muscle electrical activity from the biceps and triceps.
2- IMU Sensors: Measure upper-arm and forearm orientation and movement.
3- EEG Acquisition: Provides brain activity data through a separate acquisition system.
4- nRF52840: Acts as the central controller for the wearable EMG and IMU subsystem.
5- Bluetooth Low Energy (BLE): Supports wireless communication between the wearable controller and the computer.
6- Local Processing: Handles signal preprocessing, feature extraction, and machine learning inference.
7- Visualization: Presents movement-related measurements and processing results.

Technology Stack

1. Programming Language: Python
2. Data Processing: NumPy, Pandas
3. Machine Learning: Scikit-learn, XGBoost
4. Signal Processing: SciPy
5. Data Formats: CSV, NumPy arrays
6. Wireless Communication: Bluetooth Low Energy (BLE)
7. Embedded Hardware: Nordic nRF52840
8. BLE Communication: Bleak
9. Cryptography: Python Cryptography
10. Data Integrity: SHA-256
11. Testing: Python unittest
12. Version Control: Git and GitHub

The technology list includes tools used in the current prototypes and project workflow; not every component is integrated into the final system.

Cybersecurity and Privacy

Cybersecurity is a core part of NeuroBridge's development.

The project explores and tests:

1- Role-Based Access Control (RBAC).
2- AES-256-GCM authenticated file encryption.
3- BLE security architecture and device authorization requirements.
4- SHA-256 file integrity verification.
5- Input validation and timestamp consistency checks.
6- HMAC-SHA-256 pseudonymization.
7- Data minimization and identity mapping separation.
8- Security testing and threat modeling based on STRIDE.

Security implementations are currently at different stages of development. Standalone prototype test results do not imply complete system integration or production readiness.

Dataset and Testing

The project uses the Biomed_SPC dataset for preliminary multimodal signal analysis and data-processing validation.

The available dataset includes EEG, EMG, and IMU recordings from healthy participants.

Synthetic datasets are also used for software testing, including:

1. Data integrity verification.
2. Input validation.
3. Access control.
4. Encryption and decryption.
5. Privacy processing.
6. Security-related edge cases.

The available dataset does not represent a clinical stroke population and cannot establish clinical effectiveness.

Current Development Status

NeuroBridge is under active research and development.

Current work includes:

1- Multimodal biosignal data exploration.
2- Signal validation and preprocessing.
3- Preliminary machine learning experiments.
4- BLE architecture and security analysis.
5- Standalone cybersecurity prototypes.
6- Privacy and data integrity testing.

Hardware integration, full application integration, and clinical validation remain outside the scope of the currently verified implementation.

Project Goals

1. Explore multimodal biosignal integration for personalized upper-limb rehabilitation.
2. Investigate machine learning approaches for movement-related signal analysis.
3. Develop a secure and privacy-conscious data-processing architecture.
4. Evaluate software components through reproducible testing.
5. Identify limitations and requirements for future hardware and clinical development.

Disclaimer

NeuroBridge is a research and development project. It is not a certified medical device and is not intended to replace professional medical diagnosis, treatment, or rehabilitation supervision.
The available dataset does not represent a clinical stroke population and cannot establish clinical effectiveness.

