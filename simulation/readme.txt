simnibs4 example dataset
------------------------

The datatset is shared under the CC BY-NC 4.0 - Creative Commons Attribution-NonCommercial 4.0 International - license
https://creativecommons.org/licenses/by-nc/4.0/

You can share and adapt the dataset if you do not use it for any commercial purposes. Please cite when publishing work using the dataset:
   Thielscher, A., Antunes, A. and Saturnino, G.B. (2015)
   Field modeling for transcranial magnetic stimulation: a useful tool to understand the physiological effects of TMS? 
   IEEE EMBS 2015, Milano, Italy

version 1 of the ernie and MNI152 models were created using charm (Puonti et al, NI, 2020).

version 2
* ernie was created using an improved version of charm, which used pial and white matter surfaces reconstructed by FreeSurfer(https://surfer.nmr.mgh.harvard.edu/) to improve the representation of small sulci in the head mesh. In addition, the tetrahedral quality of the mesh was increased to improve numerical accuracy of the FEM calculations.
* MNI152 was remeshed to increase the tetrahedral quality. The anatomy was kept unchanged.

version 2.1
* fixed surface labels in sphere.msh
* added license

A. Thielscher, 2024