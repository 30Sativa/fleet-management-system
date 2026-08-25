# Architecture Decision Records

One file per decision that someone will later ask "why is it like this?" about.

## Format

```
NNNN-short-slug.md

# ADR-NNNN: Title

## Context      what forced a choice
## Decision     what we chose (present tense, not "we will")
## Consequences positive / negative, honestly
```

## When to write one

Write an ADR when the decision:

- constrains how other people write code (a layering rule, a sensor hierarchy),
- would be expensive to reverse (database choice, deployment model),
- looks wrong at first glance and needs its reason recorded, or
- was argued about.

Do **not** write one for: renaming a function, fixing a bug, adding a button,
adding a test, bumping a patch version.

## Index

| ADR | Decision | Status |
|---|---|---|
| [0001](0001-lidar-primary-astra-supplementary.md) | LiDAR is the navigation backbone; the Astra Pro is supplementary | accepted |
| [0002](0002-manual-stlink-flash-no-can-bootloader.md) | STM32 firmware is flashed manually over ST-Link | accepted |
| [0003](0003-deploy-robot-via-docker-image.md) | The robot runs a prebuilt Docker image, not a build on the miniPC | accepted |

<!-- TODO(Duy): những decision sắp tới đáng viết ADR:
     - chọn transport cho contract robot <-> backend
     - chọn database cho backend
     - chọn model AI cho assistant dưới ràng buộc i3-7100T / 8GB / không GPU
     - monorepo vs multi-repo (nếu muốn ghi lại lý do gộp)
-->
