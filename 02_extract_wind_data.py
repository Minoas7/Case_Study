import geopandas as gpd
import rasterio
from shapely.geometry import box

# 1. Read the geographical bounds and CRS of our nDSM
ndsm_file = "nDSM_obstacles_2680-1237.tif"
with rasterio.open(ndsm_file) as src:
  bounds = src.bounds  # (left, bottom, right, top)
  crs = src.crs
  print(f"nDSM Bounds: {bounds}")
  print(f"nDSM CRS: {crs}")

# 2. Load the Swiss Wind Atlas GeoPackage
gpkg_file = "Windatlas_50.gpkg"
print("Loading the Swiss Wind Atlas GeoPackage...")
gdf_wind = gpd.read_file(gpkg_file, layer="HEIGHT_LEVEL_50_CH")

# 3. Align Coordinate Reference System (CRS) if they differ
if gdf_wind.crs != crs:
  print(f"Converting Wind Atlas CRS to {crs}...")
  gdf_wind = gdf_wind.to_crs(crs)

# 4. Create Bounding Box geometry for Adliswil
bbox_geom = box(bounds.left, bounds.bottom, bounds.right, bounds.top)
bbox_gdf = gpd.GeoDataFrame(geometry=[bbox_geom], crs=crs)

# 5. Spatial Clip of the wind data to our study area
local_wind = gpd.clip(gdf_wind, bbox_gdf)
print(
    f"Found {len(local_wind)} wind grid elements in the study area."
)

# 6. Check and print the directional data per sector
if not local_wind.empty:
  # Get the first element (or calculate average if covered by multiple pixels)
  row = local_wind.iloc[0]
  print("\n==============================================")
  print("   DIRECTIONAL WIND DATA FOR ADLISWIL")
  print("==============================================")
  print(f"Total mean wind speed (V_MEAN): {row['V_MEAN']:.2f} m/s")
  print(
      f"Total Weibull distribution -> Scale A: {row['WEI_A']:.2f},"
      f" Shape k: {row['WEI_K']:.2f}"
  )
  print("-" * 46)
  print(f"{'Sector':<10} | {'Frequency (%)':<15} | {'Weibull A':<10} | {'k'}")
  print("-" * 46)

  sectors = range(0, 360, 30)
  for s in sectors:
    freq = row.get(f"FREQ_{s}", 0)
    a_par = row.get(f"WEI_A_{s}", 0)
    k_par = row.get(f"WEI_K_{s}", 0)
    print(f"{s:3d}°      | {freq:12.2f}%    | {a_par:8.2f}   | {k_par:.2f}")

  print("==============================================")

  # Save the local subset to a new gpkg file for the next AEP calculation step
  output_gpkg = "Adliswil_wind_sectors.gpkg"
  local_wind.to_file(output_gpkg, driver="GPKG")
  print(f"\nLocal data successfully saved to: {output_gpkg}")
else:
  print(
      "Warning: No data found in the area. Check the file coordinates."
  )