# Facades from street photos (Mapillary): plan

Goal (the owner, 2026-11-09): a building's look comes from real photos, not from a guess.
Source: Mapillary street photos (CC BY-SA 4.0, credited), not Google (its terms forbid storing and converting
its imagery; the upstream owner refused Yandex and 2GIS for the same reason, GitHub #139).

## Pipeline (offline, per city; the game only loads its results)
1. **Photos**: Mapillary Graph API v4, images in the city's tiles with `computed_geometry`,
   `computed_compass_angle`, `computed_rotation`, `camera_type`, `camera_parameters`, `thumb_2048_url`,
   `sfm_cluster`; perspective and 360 cameras.
2. **Facades**: building footprints and heights (Overture / OSM); each footprint edge is a wall rectangle
   (ground to eaves).
3. **Visibility**: for each wall, the photos that see it: in the camera's field of view, facing it (angle
   < ~60 deg), within ~60 m, not hidden by another building (ray test against the footprints).
4. **Rectification**: the wall's four corners projected into the photo (the camera's pose and intrinsics;
   360 photos: equirectangular to a perspective view first), a homography to a front view at a fixed px/m.
5. **Cleaning**: Mapillary's segmentation (cars, people, trees, poles) masks occluders; several photos of one
   wall merged per pixel (median of the unmasked ones); a quality score (sharpness, coverage, angle).
6. **Parameters** (step one, robust): from the rectified facade: wall colour, material class (panel / brick /
   plaster / glass / stone), floor count, window grid (bays, window size), shop ground floor. A classifier
   (small CNN on the RTX 5080) for the material; the window grid from the facade's periodicity.
7. **Textures** (step two, where the photos are good): the rectified, cleaned facade itself as the wall's
   texture, tiled per floor where it repeats; the procedural look where they are not.
8. **Output**: per building id a compact record (colour, material, floors, bays, texture id) in the map
   cache; buildings.plan() takes it over its guesses; the region style stays the fallback.

## Pilot
Khreshchatyk, Kyiv (Maidan to Bessarabska, ~50.444-50.451 N, 30.518-30.526 E): coverage, how many walls get a
usable photo, how clean the rectified facades come out.

## Pilot result (2026-11-09): no open street photos of Ukraine
- Mapillary has the metadata of Ukraine's photos (Kyiv's pilot box: 16,737 with computed poses; 344 of 1,868 walls
  seen, 227 of the 1,044 walls of 15 m and more), but **no image of any of them**: no thumbnail field for any
  photo in Kyiv, Lviv, Uzhhorod or Kharkiv, while Warsaw, Chisinau, Minsk and Baltimore return theirs (the same token).
  Most likely a wartime restriction on Ukraine's imagery.
- Panoramax: 1 photo in central Kyiv, 0 in Lviv, Odesa, Dnipro. KartaView's API did not answer.
- The camera model (OpenSfM angle-axis, world ENU, x right / y down / z forward; perspective and fisheye) checks
  out: the heading from computed_rotation matches computed_compass_angle to 0.00 deg.
- So the pipeline works only where Mapillary serves images (most of the world outside Ukraine); Ukraine keeps the
  region style until its imagery opens again or another source is found.
