# SpectraSuite: Integrated FT-IR and XRD Analysis Toolkit


_No Origin Software_ Don't worry


**SpectraSuite** is a lightweight, open-source Python application I designed (with help of Gemini for refinig) for the rapid processing, visualization, and analysis of Vibrational (FT-IR) and Diffractive (XRD) spectroscopy data. It provides a unified, interactive interface to help researchers move directly from raw diffractometer/spectrometer data to publication-quality results.

## Key Features

### FT-IR Analysis
* **Smart Peak Detection:** Automatic identification of absorption bands and transmittance valleys.
* **Baseline Correction:** Asymmetric Least Squares (ALS) algorithm and interactive manual baseline subtraction.
* **Optical Unit Conversion:** Instant mathematical toggling between % Transmittance and Absorbance units.
* **Data Smoothing:** Built-in Savitzky-Golay filtering for quick noise reduction.

### XRD Analysis
* **Crystallite Size Estimation:** Integrated Scherrer Equation calculator.
* **Grain Size Distribution:** Automatic Gaussian fitting of crystallite sizes derived from multiple peaks.
* **Smart Snap:** Interactive peak picking that automatically "snaps" to the local maximum for precise 2θ and FWHM determination.

### Export & Session Management
* **Data Export:** Instantly export your picked peaks, integrated areas, and deconvoluted data to structured Excel (`.xlsx`) files.
* **State Persistence:** Save and load full analytical sessions (`.json`), including your custom baseline points and manual annotations, so you never lose your work.

## Installation

SpectraSuite is built entirely in Python and is cross-platform (Windows, macOS, Linux).

1. **Clone the repository:**
   ```bash
   git clone https://github.com/YOUR_USERNAME/SpectraSuite.git
   cd SpectraSuite

2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt

3. **Run the application:**
   ```bash
   python launcher1.py

## **Software Architecture**

The suite utilizes a highly modular design to ensure stable, isolated data processing:

**_launcher1.py:_** A PySide6 dashboard for routing the user to the correct analytical module.

**_gui.py_** and annotations.py: The Tkinter/Matplotlib frontend for interactive data visualization.

**_processing.py:_** The mathematical engine handling ALS baselines, peak finding, and Gaussian curve fitting.

**_config.py and session.py:_** Global state management ensuring smooth cross-window data persistence.

**_ir.py and xrd.py:_** Data-loading logic built to handle various diffractometer and spectrometer file formats.

## **Citation / DOI**

If you use this software in your research, please cite it using the following DOI: ![DOI](https://zenodo.org/badge/1232613207.svg) / https://doi.org/10.5281/zenodo.20089982


## **License**

This project is licensed under the MIT License.
