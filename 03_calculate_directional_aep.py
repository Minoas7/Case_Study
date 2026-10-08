import geopandas as gpd
import numpy as np
import rasterio
import rasterio.features
import scipy.ndimage

print("1. Loading nDSM data (0.5m obstacles)...")
ndsm_file = "nDSM_obstacles_2680-1237.tif"
with rasterio.open(ndsm_file) as src:
  ndsm_data = src.read(1)
  meta = src.meta
  crs = src.crs
  transform = src.transform
  out_shape = ndsm_data.shape
  pixel_size = transform[0]

print("2. Loading directional wind data...")
gpkg_wind = "Adliswil_wind_sectors.gpkg"
gdf_wind = gpd.read_file(gpkg_wind)
if gdf_wind.crs != crs:
  gdf_wind = gdf_wind.to_crs(crs)

sectors = range(0, 360, 30)

print("3. Rasterization of wind data to 0.5m grid...")
raster_wind_params = {}
for s in sectors:
  freq_col, a_col, k_col = f"FREQ_{s}", f"WEI_A_{s}", f"WEI_K_{s}"
  
  shapes_freq = [(geom, val / 100.0) for geom, val in zip(gdf_wind.geometry, gdf_wind[freq_col])]
  r_freq = rasterio.features.rasterize(shapes_freq, out_shape=out_shape, transform=transform, fill=0.0, dtype=np.float32)
  
  shapes_a = [(geom, val) for geom, val in zip(gdf_wind.geometry, gdf_wind[a_col])]
  r_a = rasterio.features.rasterize(shapes_a, out_shape=out_shape, transform=transform, fill=0.0, dtype=np.float32)
  
  shapes_k = [(geom, val) for geom, val in zip(gdf_wind.geometry, gdf_wind[k_col])]
  r_k = rasterio.features.rasterize(shapes_k, out_shape=out_shape, transform=transform, fill=1.8, dtype=np.float32)
  
  raster_wind_params[s] = {"freq": r_freq, "A": r_a, "k": r_k}

print("4. Power Curve Definition (300 kW)...")
u_table = np.array([0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16])
p_table = np.array([0, 0, 0, 1.2, 13.4, 33.6, 66.4, 109.9, 160.8, 217.5, 281.6, 300, 300, 300, 300, 300, 300])

def get_power_from_curve(v_array):
  power = np.interp(v_array, u_table, p_table, left=0.0, right=300.0)
  return np.where(v_array > 16.0, 0.0, power)

# NEW HEIGHT PARAMETERS
hub_height = 29.0      # The wind turbine hub height
ref_height = 50.0      # The reference height of the Wind Atlas data
alpha = 0.143
hours_per_year = 8760
v_bins = np.arange(0, 26, 1.0)
power_curve_bins = get_power_from_curve(v_bins)

ndsm_clipped = np.clip(ndsm_data, 0, hub_height)

print("5. Downwind Obstacle Shadow (Wake Effect) & Sector AEP Calculation...")
total_aep = np.zeros_like(ndsm_data, dtype=np.float32)

wake_distance = 150.0  
step_m = 5.0           
decay_factor = 0.015   

for s, params in raster_wind_params.items():
  freq_grid = params["freq"]
  if np.max(freq_grid) == 0:
    continue

  dy_m = np.cos(np.radians(s))
  dx_m = -np.sin(np.radians(s))
  shadow_grid = np.copy(ndsm_clipped)
  
  for d in np.arange(step_m, wake_distance, step_m):
    shift_y = (d * dy_m) / pixel_size
    shift_x = (d * dx_m) / pixel_size
    decay = np.exp(-decay_factor * d)
    
    shifted_ndsm = scipy.ndimage.shift(ndsm_clipped, shift=(shift_y, shift_x), mode='constant', cval=0.0)
    shadow_grid = np.maximum(shadow_grid, shifted_ndsm * decay)
  
  effective_height = hub_height - shadow_grid
  effective_height = np.maximum(effective_height, 5.0)
  
  # ATTENTION: Weibull (A) adjustment is now relative to the 50m Wind Atlas height
  A_local_grid = params["A"] * (effective_height / ref_height) ** alpha
  sector_energy_pixel = np.zeros_like(ndsm_data, dtype=np.float32)

  for i, v in enumerate(v_bins):
    p_power = power_curve_bins[i]
    if p_power == 0: continue
    
    safe_A = np.maximum(A_local_grid, 0.1)
    safe_k = np.maximum(params["k"], 0.1)
    pdf = (safe_k / safe_A) * ((v / safe_A) ** (safe_k - 1.0)) * np.exp(-((v / safe_A) ** safe_k))
    sector_energy_pixel += p_power * pdf

  total_aep += sector_energy_pixel * freq_grid * hours_per_year

print("6. Saving final AEP map with integrated Wake Effect...")
meta.update(dtype=rasterio.float32, count=1)
output_tif = "AEP_Adliswil_300kW_29m_WakeEffect.tif"
with rasterio.open(output_tif, "w", **meta) as dst:
  dst.write(total_aep.astype(rasterio.float32), 1)

print(f"Success! The new map is: {output_tif}")