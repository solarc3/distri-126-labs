#!/usr/bin/env python3
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import sys

def load_scaling():
    try:
        data = np.loadtxt('scaling_analysis.dat', comments='#')
    except OSError:
        print("Error: No se encontro 'scaling_analysis.dat'. Ejecute primero el benchmark.")
        sys.exit(1)
    if data.ndim == 1:
        data = data.reshape(1, -1)
    return data

def load_chunk():
    try:
        data = np.loadtxt('chunk_benchmark.dat', skiprows=1)
    except OSError:
        print("Aviso: 'chunk_benchmark.dat' no encontrado. Omitiendo grafico de chunk.")
        return None
    if data.ndim == 1:
        data = data.reshape(1, -1)
    return data

def load_energy():
    try:
        data = np.loadtxt('physics_metrics.dat', skiprows=1)
    except OSError:
        print("Aviso: 'physics_metrics.dat' no encontrado. Omitiendo grafico de energia.")
        return None
    if data.ndim == 1:
        data = data.reshape(1, -1)
    return data


def main():
    scaling = load_scaling()
    threads = scaling[:, 0].astype(int)
    time_scaling = scaling[:, 1]
    speedup = scaling[:, 2]
    efficiency = scaling[:, 3]
    serial_fraction = scaling[:, 4]
    theoretical_amdahl = scaling[:, 5]

    chunk_data = load_chunk()
    energy_data = load_energy()

    fig, axes = plt.subplots(3, 2, figsize=(14, 18))
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
    ax3.plot(threads, time_scaling, 'mo-', linewidth=2, markersize=8)
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

    # (5) Tiempo vs Tamanio de Chunk para distintos Schedules
    ax5 = axes[2, 0]
    if chunk_data is not None:
        schedules = chunk_data[:, 0].astype(int)
        chunks = chunk_data[:, 1].astype(int)
        times = chunk_data[:, 2]
        sched_names = ['static', 'dynamic', 'guided']
        colors = ['blue', 'red', 'green']
        markers = ['o', 's', '^']
        for s in range(3):
            mask = schedules == s
            if np.any(mask):
                ax5.plot(chunks[mask], times[mask], color=colors[s], marker=markers[s],
                         linewidth=2, markersize=8, label=sched_names[s])
        ax5.set_xlabel('Tamanio de chunk', fontsize=12)
        ax5.set_ylabel('Tiempo medio (s)', fontsize=12)
        ax5.set_title('Tiempo vs Chunk para distintos Schedules (4 hilos)')
        ax5.legend()
    else:
        ax5.text(0.5, 0.5, 'Datos no disponibles', ha='center', va='center',
                 transform=ax5.transAxes, fontsize=14, color='gray')
        ax5.set_title('Tiempo vs Chunk (no disponible)')
    ax5.grid(True, alpha=0.3)

    # (6) Energia Total vs Tiempo (pasos de simulacion)
    ax6 = axes[2, 1]
    if energy_data is not None:
        steps = energy_data[:, 0].astype(int)
        total_energy = energy_data[:, 3]
        ax6.plot(steps, total_energy, 'b-', linewidth=2)
        ax6.set_xlabel('Paso de simulacion', fontsize=12)
        ax6.set_ylabel('Energia total (K + U)', fontsize=12)
        ax6.set_title('Conservacion de Energia (Euler Explicito)')
        # Add horizontal line at initial energy for reference
        ax6.axhline(y=total_energy[0], color='gray', linestyle=':', alpha=0.5)
    else:
        ax6.text(0.5, 0.5, 'Datos no disponibles\nEjecute ./nbody_sim primero',
                 ha='center', va='center', transform=ax6.transAxes,
                 fontsize=14, color='gray')
        ax6.set_title('Conservacion de Energia (no disponible)')
    ax6.grid(True, alpha=0.3)

    plt.tight_layout()
    plt.savefig('performance_plots.png', dpi=150)
    plt.close()
    print("Graficos generados exitosamente en 'performance_plots.png'")


if __name__ == '__main__':
    main()
