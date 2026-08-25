# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- **[Infraestructura]** Plantilla de Pull Request (`.github/pull_request_template.md`).
- **[Infraestructura]** Pipeline de CI/CD para linting y pruebas unitarias (`.github/workflows/ci.yml`).
- **[Infraestructura]** Agentes de IA adaptados a Python para revisión de Documentación, Bugs y MRs.
- **[Infraestructura]** Makefile con targets comunes (`make test`, `make compose-delitos`, etc).
- **[Infraestructura]** `Dockerfile` base y `docker-compose.yml` multi-perfil (delitos/aire).
- **[Infraestructura]** Scripts de inicialización en Slurm (`run_cluster.slurm`, `bootstrap_peer.sh`).
- **[Infraestructura]** Script generador de issues base (`scripts/create_lab3_issues.py`).

### Changed
- README actualizado con las instrucciones base para Laboratorio 3 y roles asignados.
