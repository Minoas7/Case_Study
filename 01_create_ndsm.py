import rasterio
import numpy as np
import os

# Define the file names. 
# Since the script is in the same folder, the name is enough, no need for the full path (e.g., C:/...)
surface_file = "swisssurface3d-raster_2024_2680-1237_0.5_2056_5728.tif"
alti_file = "swissalti3d_2026_2680-1237_0.5_2056_5728.tif"
output_ndsm_file = "nDSM_obstacles_2680-1237.tif"

print("Loading data (Surface and Terrain)...")

try:
    # Open the files
    with rasterio.open(surface_file) as src_surface, rasterio.open(alti_file) as src_alti:
        
        # Read the data (band 1)
        surface_data = src_surface.read(1)
        alti_data = src_alti.read(1)
        
        # Keep the surface metadata to pass it to the new file
        meta = src_surface.meta

    print("Calculating obstacle height (nDSM = Surface - Terrain)...")
    
    # The mathematical operation
    ndsm_data = surface_data - alti_data
    
    # Filtering: If anything is negative (e.g., due to radar error), set it to 0.
    ndsm_data = np.where(ndsm_data < 0, 0, ndsm_data)

    print(f"Saving the result to: {output_ndsm_file}")
    
    # Write the new file
    with rasterio.open(output_ndsm_file, 'w', **meta) as dst:
        dst.write(ndsm_data, 1)
        
    print("Success! The file has been created.")

except Exception as e:
    print(f"An error occurred: {e}")