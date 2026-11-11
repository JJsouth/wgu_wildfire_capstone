# wgu_wildfire_capstone

This repository stores the code for my WGU Capstone Project: Determining Whether Wildfire Burn Area is Affected by the Initial Ignition Source

Data was obtained from the USFA Research Data Archive (note the SQLite database file must be renamed to “wildfire_data” to operate properly in the script): Forest Service Research Data Archive https://www.fs.usda.gov/rds/archive/catalog/RDS-2013-0009.7

GACC shape data is available here: https://data-nifc.opendata.arcgis.com/datasets/nifc::national-gacc-boundaries-public/about

These data were collected using funding from the U.S. Government and can be used without additional permissions or fees.
Short, Karen C. 2026. Spatial wildfire occurrence data for the United States, 1992-2024 [FPA_FOD_20260615]. 7th Edition. Fort Collins, CO: Forest Service Research Data Archive. https://doi.org/10.2737/RDS-2013-0009.7

This project sought to determine whether there are statistical differences in the size of wildfire burn areas between human-caused ignitions and naturally caused ignitions. Determining the difference can provide regional leaders with their local danger group and where to prioritize resource allocation to mitigate initial ignition danger or reduce fire spread.
The project focused on understanding whether the initial ignition source affects the final burn area. The project analyzed the regions where fires burned and reported the count of human ignition subtypes, such as power transmission, smoking, or firearm use. Additional factors that affect wildfire growth and damage, such as weather patterns, area fuels, suppression policy, and climate change, fell outside the scope of this project.
The analysis was built in VScode using the Python programming language, Conda Environment Manager, Jupyter Notebooks, and the following packages: sqlite3, numpy, pandas, matplotlib, ipykernal, geopandas, scipy, pptx. 
Using pandas, the dataset was loaded from a SQLite database, then joined using geopandas to sort each fire into ten geographic regions used by the Interagency Fire Command Center. 

Then each region went through the processing pipeline steps:
  1) Run statistical comparison tests for each region.
  2) Create data visuals for each region.
  3) Create a PowerPoint for each region using the generated visuals.
  4) Report policy recommendations and conclusions for each region.


