#!/usr/bin/env python3
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import sys

def as_2d(data):
    if data.ndim == 1:
        return data.reshape(1, -1)
    return data

def as_records(data):
    if data is None:
        return None
    if data.shape == ():
        return np.array([data], dtype=data.dtype)
    return data

def load_optional_numeric(path, skiprows=1):
    try:
        data = np.loadtxt(path, skiprows=skiprows)
    except OSError:
        print(f"Aviso: '{path}' no encontrado. Omitiendo grafico asociado.")
        return None
    except ValueError as exc:
        print(f"Aviso: no se pudo leer '{path}' ({exc}). Omitiendo grafico asociado.")
        return None
    return as_2d(data)

def load_optional_table(path):
    try:
        data = np.genfromtxt(path, names=True, dtype=None, encoding='utf-8')
    except OSError:
        print(f"Aviso: '{path}' no encontrado. Omitiendo grafico asociado.")
        return None
    except ValueError as exc:
        print(f"Aviso: no se pudo leer '{path}' ({exc}). Omitiendo grafico asociado.")
        return None
    return as_records(data)

def load_scaling():
    try:
        data = np.loadtxt('scaling_analysis.dat', comments='#')
    except OSError:
        print("Error: No se encontro 'scaling_analysis.dat'. Ejecute primero el benchmark.")
        sys.exit(1)
    except ValueError as exc:
        print(f"Error: no se pudo leer 'scaling_analysis.dat' ({exc}).")
        sys.exit(1)
    return as_2d(data)

def load_chunk():
    return load_optional_numeric('chunk_benchmark.dat')

def load_energy():
    return load_optional_numeric('energy_timeseries.dat')

def amdahl_curve(threads, speedup):
    mask = threads > 1
    if not np.any(mask):
        return np.ones_like(speedup), 1.0

    p = threads[mask].astype(float)
    s = speedup[mask].astype(float)
    fractions = ((1.0 / s) - (1.0 / p)) / (1.0 - (1.0 / p))
    fractions = fractions[np.isfinite(fractions)]
    if fractions.size == 0:
        serial_fraction = 0.0
    else:
        serial_fraction = float(np.median(np.clip(fractions, 0.0, 1.0)))

    model = 1.0 / (serial_fraction + (1.0 - serial_fraction) / threads.astype(float))
    return model, serial_fraction

def show_missing(ax, title, message='Datos no disponibles'):
    ax.text(0.5, 0.5, message, ha='center', va='center',
            transform=ax.transAxes, fontsize=12, color='gray')
    ax.set_title(title)

def plot_named_bars(ax, data, label_col, value_col, title, ylabel):
    if data is None or len(data) == 0:
        show_missing(ax, title)
        return

    labels = [str(x) for x in data[label_col]]
    values = np.asarray(data[value_col], dtype=float)
    x = np.arange(len(labels))
    ax.bar(x, values, color='#4c78a8')
    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=20, ha='right')
    ax.set_ylabel(ylabel, fontsize=12)
    ax.set_title(title)


def main():
    scaling = load_scaling()
    threads = scaling[:, 0].astype(int)
    time_scaling = scaling[:, 1]
    speedup = scaling[:, 2]
    efficiency = scaling[:, 3]
    serial_fraction = scaling[:, 4]
    theoretical_amdahl, amdahl_serial_fraction = amdahl_curve(threads, speedup)

    chunk_data = load_chunk()
    energy_data = load_energy()
    schedule_data = load_optional_table('schedule_benchmark.dat')
    sync_data = load_optional_table('sync_benchmark.dat')
    energy_sync_data = load_optional_table('energy_sync_benchmark.dat')
    task_work_data = load_optional_table('task_work_benchmark.dat')

    fig, axes = plt.subplots(4, 2, figsize=(14, 24))
    fig.suptitle('Analisis de Rendimiento - Simulador N-Body OpenMP', fontsize=16, y=0.995)

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
    ax4.set_title(f'Curva Practica vs Teorica (f serial={amdahl_serial_fraction:.4f})')
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
        ax5.set_title('Tiempo vs Chunk para distintos Schedules')
        ax5.legend()
    else:
        show_missing(ax5, 'Tiempo vs Chunk')
    ax5.grid(True, alpha=0.3)

    # (6) Comparacion de schedules
    ax6 = axes[2, 1]
    if schedule_data is not None:
        plot_named_bars(ax6, schedule_data, 'Schedule', 'MeanTime',
                        'Tiempo por Schedule', 'Tiempo medio (s)')
    elif energy_data is not None:
        steps = energy_data[:, 0].astype(int)
        total_energy = energy_data[:, 3]
        ax6.plot(steps, total_energy, 'b-', linewidth=2)
        ax6.set_xlabel('Paso de simulacion', fontsize=12)
        ax6.set_ylabel('Energia total (K + U)', fontsize=12)
        ax6.set_title('Conservacion de Energia (Euler Explicito)')
        # Add horizontal line at initial energy for reference
        ax6.axhline(y=total_energy[0], color='gray', linestyle=':', alpha=0.5)
    else:
        show_missing(ax6, 'Tiempo por Schedule')
    ax6.grid(True, alpha=0.3)

    # (7) Comparacion de sincronizacion del integrador
    ax7 = axes[3, 0]
    plot_named_bars(ax7, sync_data, 'SyncType', 'MeanTime',
                    'Tiempo por Estrategia de Sincronizacion', 'Tiempo medio (s)')
    ax7.grid(True, alpha=0.3)

    # (8) Contencion real o tasking con trabajo
    ax8 = axes[3, 1]
    if energy_sync_data is not None:
        plot_named_bars(ax8, energy_sync_data, 'SyncMethod', 'MeanTime',
                        'Contencion Real: Critical vs Atomic vs Reduction', 'Tiempo medio (s)')
    elif task_work_data is not None:
        labels = [f"{row['TaskType']}/{row['SyncType']}" for row in task_work_data]
        values = np.asarray(task_work_data['MeanTime'], dtype=float)
        x = np.arange(len(labels))
        ax8.bar(x, values, color='#f58518')
        ax8.set_xticks(x)
        ax8.set_xticklabels(labels, rotation=25, ha='right')
        ax8.set_ylabel('Tiempo medio (s)', fontsize=12)
        ax8.set_title('Task vs Parallel-For con Trabajo')
    else:
        show_missing(ax8, 'Contencion Real')
    ax8.grid(True, alpha=0.3)

    plt.tight_layout(rect=[0.0, 0.0, 1.0, 0.985])
    plt.savefig('performance_plots.png', dpi=150)
    plt.close()
    print("Graficos generados exitosamente en 'performance_plots.png'")


if __name__ == '__main__':
    main()
