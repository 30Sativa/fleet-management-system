# ADR-0001: LiDAR is the navigation backbone, the Astra Pro is supplementary

## Context

The robot carries both an RPLiDAR A3M1 and an Orbbec Astra Pro RGB-D camera.
Either could in principle feed localization and mapping. The Astra Pro was
brought up over four phases and works, which makes it tempting to lean on it.

Two things argue against that. The Astra Pro's depth stream is noisy at the
edges and degrades badly in outdoor light, and its USB throughput was already
a bottleneck during bring-up. AMCL and SLAM behaviour on a 2D laser scan is
well understood and is what the Nav2 stack is tuned for out of the box.

## Decision

The RPLiDAR feeds `/scan` and is the input for SLAM, AMCL, and both the local
and global costmaps. Wheel encoders plus IMU produce `/odom` and the
`odom -> base_link` transform.

The Astra Pro contributes:

- `/camera/depth/points` into the **local costmap only**, for 3D obstacles a
  2D scan plane misses (tables, overhangs, low bars),
- RGB into person detection, which lowers the Nav2 speed limit near people.

The Astra Pro is never a localization source, never feeds the global costmap,
and navigation must still work with the camera absent.

## Consequences

Positive:

- Navigation keeps working if the camera fails, is unplugged, or saturates USB.
- Localization behaviour matches what Nav2 expects, so tuning guidance applies.
- Camera work can proceed in phases without blocking navigation work.

Negative:

- Obstacles that are invisible to both the laser plane and the depth cone
  (a thin wire, glass) remain undetected.
- Two obstacle sources feeding one local costmap means costmap tuning has to
  account for depth-sensor noise.
- The camera's value is harder to demonstrate, since it never shows up in a
  localization metric.
