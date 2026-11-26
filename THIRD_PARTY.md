# Third-party software

## Compiled into `native/ps5bridge.dll`

| Project | Version | License | Source |
|---|---|---|---|
| chiaki-ng (libchiaki) | v1.10.0 | AGPL-3.0 with OpenSSL exception | https://github.com/streetpea/chiaki-ng |
| Mbed TLS | 2.28.10 | Apache-2.0 | https://github.com/Mbed-TLS/mbedtls |
| nanopb | chiaki-ng submodule | zlib | https://github.com/nanopb/nanopb |
| Jerasure | chiaki-ng submodule | BSD-3-Clause | https://github.com/streetpea/jerasure |
| gf-complete | chiaki-ng submodule | BSD-3-Clause | https://github.com/streetpea/gf-complete |

The build changes one chiaki-ng file at compile time (`lib/src/rpcrypt.c`,
a 16-byte HMAC buffer enlarged to 32 bytes) and replaces its internet
holepunch code with `native/holepunch_stub.c`. See
[docs/07-building.md](docs/07-building.md).

## Python packages (installed by `requirements.txt`)

| Package | License |
|---|---|
| aiohttp | Apache-2.0 AND MIT |
| av (PyAV, bundles FFmpeg) | BSD-3-Clause (FFmpeg: LGPL) |
| Pillow | MIT-CMU |
| mcp | MIT |
| psnawp | MIT |
| requests | Apache-2.0 |

The DDP discovery and wake message formats follow chiaki-ng and
pyremoteplay (https://github.com/ktnrg45/pyremoteplay, GPL-3.0).

## GTA6 PS5 AI additions

| Component | License | Source |
|---|---|---|
| Ultralytics YOLO11 (`ultralytics`, `yolo11n.pt` weights, downloaded on first run) | AGPL-3.0 | https://github.com/ultralytics/ultralytics |
| PyTorch | BSD-3-Clause | https://github.com/pytorch/pytorch |
| Claude Code CLI (`claude`, the bot brain; uses your own Claude subscription) | Anthropic terms | https://claude.com/claude-code |

Grand Theft Auto VI is a trademark of Rockstar Games / Take-Two Interactive. PlayStation and PS5 are trademarks of Sony Interactive Entertainment. This project is not affiliated with or endorsed by them.
