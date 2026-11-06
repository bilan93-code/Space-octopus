# Motor CAD and Gmsh–Elmer study

Download the standalone detailed report and the nominal motor assembly:

- [New Gmsh–Elmer design and analysis report (PDF)](downloads/Motor_Gmsh_Elmer_Design_Study.pdf)
- [Motor assembly in millimetres (STEP)](downloads/Motor_Gmsh_Elmer_Candidate_mm.step)
- [Executed Gmsh/Elmer validation model handoff (ZIP)](downloads/Motor_Gmsh_Elmer_Validation_Models.zip)
- [Download hashes and file sizes](downloads/Motor_Gmsh_Elmer_download_manifest.json)

The 12.2 A/120°C eight-position study gives 4.900 N·m mean electromagnetic torque;
after the assumed 18 W loss allowance, the estimated actuator mean is 233 N·m
at 63:1 and 80% efficiency. A separate 13 A check supplies sampled-trough control
headroom. Continuous 22 A hot holding reaches 154.7°C and fails the assumed 130°C
winding limit. Material strength, irreversible demagnetization, installed
vibration and manufacturing qualification remain conditional or unqualified;
read the report's acceptance matrix.

The 143-solid STEP assembly uses millimetres. Solver meshes/decks use SI metres.
The model archive contains principal import meshes, native Elmer meshes and
relative case cards, the structural fault deck, result tables and reproduction
source. Coil solids are stranded-winding envelopes; bearings and threads are
dimensional envelopes. No Ansys execution or hardware test is claimed.

The earlier [dimensions report](downloads/Motor_Dimensions_and_Analysis.pdf)
remains a historical reference. The new report identifies its design revisions.
