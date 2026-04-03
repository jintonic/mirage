**MIRAGE - Medical Image Renderer Augmented Geant4 Example**

A minimalist Geant4 example that renders voxelized phantoms from medical imaging data using [pydicom][].

## Features

- _minimalistic_: it sticks with standard Geant4 components, zero extension
- _cross-platform_: it uses Python for DICOM image processing for easy installation in all major operating systems.
- _universal_: it constructs phantom from DICOM image and reads anbient geometry definition from a simple text file, and is ready to be used for different simulations
- _fast_: Python reads the image into memory, dumps the memory as it is to a binary file for C++-based Geant4 code to read in
- _educational_: it keeps things simle, short, easy to digest.
- _Direct programmatic access to NCI Imaging Data Commons (IDC)_

## Prerequisites

- Geant4 for simulation
- Python for image processing
  - [pydicom][] for DICOM image processing
  - [idc_index][] for NCI Imaging Data Commons (IDC) access
  - [textual][] for TUI

[pydicom]: https://pydicom.github.io
[idc_index]: https://github.com/ImagingDataCommons/idc-index
[textual]: https://textual.textualize.io/
