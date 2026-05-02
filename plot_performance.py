#!/usr/bin/env python3
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import sys

def main():
    try:
        data = np.loadtxt('scaling_analysis.dat', comments='#')
    except OSError:
        print("Error: No se encontro 'scaling_analysis.dat'. Ejecute primero el benchmark.")
        sys.exit(1)

    if data.ndim == 1:
        data = data.reshape(1, -1)

    threads = data[:, 0].astype(int)
    time    = data[:, 1]
    speedup = data[:, 2]
    efficiency = data[:, 3]
    serial_fraction = data[:, 4]
    theoretical_amdahl = data[:, 5]

    fig, axes = plt.subplots(2, 2, figsize=(14, 12))
    fig.suptitle('Analisis de Rendimiento - Simulador N-Body OpenMP', fontsize=16)

    # (1) Speedup vs Hilos
    ax1 = axes[0, 0]
    ax1.plot(threads, speedup, 'bo-', linewidth=2, markersize=8, label='Speedup medido')
    ax1.plot(threads, theoretical_amdahl, 'r--', linewidth=2, label='Amdahl teorico')
    ax1.plot(threads, threads.astype(float), 'g:', linewidth=1, label='Speedup ideal')
    ax1.set_xlabel('Numero de hilos', fontsize=12)
    ax1.set_ylabel('Speedup', fontsize=12)
    ax1.set_title('Speedup vs Hilos')
    ax1.legend()
    ax1.grid(True, alpha=0.3)

    # (2) Eficiencia vs Hilos
    ax2 = axes[0, 1]
    ax2.plot(threads, efficiency, 'gs-', linewidth=2, markersize=8)
    ax2.axhline(y=1.0, color='gray', linestyle=':', alpha=0.5)
    ax2.set_xlabel('Numero de hilos', fontsize=12)
    ax2.set_ylabel('Eficiencia', fontsize=12)
    ax2.set_title('Eficiencia vs Hilos')
    ax2.grid(True, alpha=0.3)

    # (3) Tiempo de ejecucion vs Hilos
    ax3 = axes[1, 0]
    ax3.plot(threads, time, 'mo-', linewidth=2, markersize=8)
    ax3.set_xlabel('Numero de hilos', fontsize=12)
    ax3.set_ylabel('Tiempo medio (s)', fontsize=12)
    ax3.set_title('Tiempo de ejecucion vs Hilos')
    ax3.grid(True, alpha=0.3)

    # (4) Curvas teorica vs practica de Amdahl
    ax4 = axes[1, 1]
    ax4.plot(threads, speedup, 'bo-', linewidth=2, markersize=8, label='Speedup practico')
    ax4.plot(threads, theoretical_amdahl, 'r^--', linewidth=2, markersize=8, label='Amdahl teorico')
    ax4.set_xlabel('Numero de hilos', fontsize=12)
    ax4.set_ylabel('Speedup', fontsize=12)
    ax4.set_title('Curva Practica vs Teorica (Ley de Amdahl)')
    ax4.legend()
    ax4.grid(True, alpha=0.3)

    plt.tight_layout()
    plt.savefig('performance_plots.png', dpi=150)
    plt.close()
    print("Graficos generados exitosamente en 'performance_plots.png'")

if __name__ == '__main__':
    main()
