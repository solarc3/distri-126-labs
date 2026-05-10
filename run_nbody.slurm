#!/bin/bash
#SBATCH --job-name=nbody_lab1
#SBATCH --partition=GPU
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=16
#SBATCH --gres=gpu:A30:1                 # <- Solicitud formal del recurso GPU de los nodos xigpu
#SBATCH --output=job-%A.out              # <- Formato de salida idéntico al del PDF
#SBATCH --error=job-%A.err

echo "Compilando el simulador..."
make clean
make

echo "Ejecutando benchmarks y generando datos..."
make analysis