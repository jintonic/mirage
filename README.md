**MIRAGE - Medical Image Renderer Augmented Geant4 Example**

A minimalist Geant4 example that renders voxelized phantoms from medical imaging data using [pydicom][].

## Features

- *minimalistic*: it sticks with standard Geant4 components, zero extension
- *cross-platform*: it uses Python for DICOM image processing for easy installation in all major operating systems.
- *universal*: it constructs phantom from DICOM image and reads anbient geometry definition from a simple text file, and is ready to be used for different simulations
- *fast*: Python reads the image into memory, dumps the memory as it is to a binary file for C++-based Geant4 code to read in
- *educational*: it keeps things simle, short, easy to digest.

## Prerequisites

- Geant4 for simulation
- Python for image processing

[pydicom]: https://pydicom.github.io
