# Credits and Acknowledgments

BioPro is built upon a robust ecosystem of open-source libraries and external services. We gratefully acknowledge the contributions of the following projects and communities:

## Core Libraries

- **[PyQt6](https://riverbankcomputing.com/software/pyqt/intro)**: The primary graphical user interface framework powering BioPro's complex, responsive, and cross-platform desktop architecture.
- **[NumPy](https://numpy.org/)**: The foundational package for high-performance array computing, driving our high-dimensional mathematical transformations and compensation matrix calculations.
- **[pandas](https://pandas.pydata.org/)**: Employed for robust data manipulation, metadata handling, and internal event storage.
- **[Matplotlib](https://matplotlib.org/)**: The engine behind our high-fidelity, manuscript-ready visualization generation, notably utilized within the Spectral Viewer.
- **[FlowKit / fcsparser](https://github.com/whitews/FlowKit)**: Critical dependencies for accurate parsing and reading of Flow Cytometry Standard (.fcs) files.

## External APIs and Databases

- **[FPbase](https://www.fpbase.org/)**: The comprehensive, open-source database for fluorescent proteins. The Spectral Viewer interfaces directly with FPbase to provide real-time retrieval of excitation, emission, and absorbance spectra, alongside vital metadata like Quantum Yield and Extinction Coefficients.

## Scientific Algorithms

- **[UMAP](https://github.com/lmcinnes/umap)**: Uniform Manifold Approximation and Projection for Dimension Reduction (McInnes, L, Healy, J, Melville, J, 2018). We utilize this state-of-the-art algorithm for non-linear dimensionality reduction and topological analysis.
- **[HDBSCAN](https://github.com/scikit-learn-contrib/hdbscan)**: Hierarchical Density-Based Spatial Clustering of Applications with Noise (Campello, R. J. G. B., Moulavi, D., Sander, J., 2013). Employed for objective, unsupervised population identification within UMAP spaces.

---
*Thank you to the vibrant open-source scientific and software engineering communities that make advanced biological analysis tools possible.*
