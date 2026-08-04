#!/usr/bin/env python3
"""genera los graficos GPU a partir
de 'blockdim_study.dat' y 'gpu_benchmark_results.dat', producidos por
`./nbody_sim --benchmark-gpu` / `make benchmark-gpu` en una maquina con GPU real
(ej. nodo GPU del cluster DIINF)."""
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

VARIANT_COLORS = {0: '#4c78a8', 1: '#f58518'}
VARIANT_LABELS = {0: 'basica (variant=0)', 1: 'shared memory (variant=1)'}


def load_table(path):
    try:
        data = np.loadtxt(path, comments='#')
    except OSError:
        print(f"Aviso: '{path}' no encontrado. Corre 'make benchmark-gpu' en una maquina con GPU primero.")
        return None
    except ValueError as exc:
        print(f"Aviso: no se pudo leer '{path}' ({exc}).")
        return None
    # Con --gpu-skip-cpu, 'gpu_benchmark_results.dat' queda con solo el header y
    # loadtxt devuelve un array vacio; sin este guard el reshape produce shape (1,0)
    # y los paneles revientan con IndexError al indexar columnas.
    if data.size == 0:
        print(f"Aviso: '{path}' no tiene filas de datos.")
        return None
    if data.ndim == 1:
        data = data.reshape(1, -1)
    return data


def show_missing(ax, title, message='Datos no disponibles (corre make benchmark-gpu en una maquina con GPU)'):
    ax.text(0.5, 0.5, message, ha='center', va='center',
            transform=ax.transAxes, fontsize=10, color='gray', wrap=True)
    ax.set_title(title)


def plot_speedup_vs_n(ax, gpu_cmp):
    if gpu_cmp is None:
        show_missing(ax, 'Speedup GPU vs CPU vs N')
        return
    N, VARIANT, _BLOCK, _CM, _CS, _GM, _GS, SPEEDUP, SPEEDUP_ERR = range(9)
    for variant in (0, 1):
        mask = gpu_cmp[:, VARIANT] == variant
        if not np.any(mask):
            continue
        sub = gpu_cmp[mask]
        order = np.argsort(sub[:, N])
        sub = sub[order]
        ax.errorbar(sub[:, N], sub[:, SPEEDUP], yerr=sub[:, SPEEDUP_ERR],
                    marker='o', linewidth=2, capsize=4,
                    color=VARIANT_COLORS[variant], label=VARIANT_LABELS[variant])
    ax.set_xlabel('N (cuerpos)')
    ax.set_ylabel('Speedup (T_CPU / T_GPU)')
    ax.set_title('Speedup GPU vs CPU vs N')
    ax.legend()


def plot_kernel_vs_end2end(ax, blockdim):
    if blockdim is None:
        show_missing(ax, 'Kernel-only vs End-to-end')
        return
    N, VARIANT, BLOCK, KMEAN, _KSTD, EMEAN, _ESTD = range(7)
    n_target = np.max(blockdim[:, N])
    mask = (blockdim[:, N] == n_target) & (blockdim[:, VARIANT] == 0)
    if not np.any(mask):
        show_missing(ax, 'Kernel-only vs End-to-end')
        return
    sub = blockdim[mask]
    sub = sub[np.argsort(sub[:, BLOCK])]
    ax.plot(sub[:, BLOCK], sub[:, KMEAN], 'o-', color='#54a24b', label='kernel-only')
    ax.plot(sub[:, BLOCK], sub[:, EMEAN], 's--', color='#e45756', label='end-to-end')
    ax.set_xlabel('blockDim.x')
    ax.set_ylabel('Tiempo medio (s)')
    ax.set_title(f'Kernel-only vs End-to-end (N={int(n_target)}, variant=0)')
    ax.legend()


def plot_time_vs_blockdim(ax, blockdim):
    if blockdim is None:
        show_missing(ax, 'Tiempo vs blockDim.x')
        return
    N, VARIANT, BLOCK, KMEAN = 0, 1, 2, 3
    n_target = np.max(blockdim[:, N])
    for variant in (0, 1):
        mask = (blockdim[:, N] == n_target) & (blockdim[:, VARIANT] == variant)
        if not np.any(mask):
            continue
        sub = blockdim[mask]
        sub = sub[np.argsort(sub[:, BLOCK])]
        ax.plot(sub[:, BLOCK], sub[:, KMEAN], 'o-', color=VARIANT_COLORS[variant], label=VARIANT_LABELS[variant])
    ax.set_xlabel('blockDim.x')
    ax.set_ylabel('Tiempo kernel-only medio (s)')
    ax.set_title(f'Tiempo vs blockDim.x (N={int(n_target)})')
    ax.legend()


def plot_basic_vs_shared(ax, gpu_cmp):
    if gpu_cmp is None:
        show_missing(ax, 'Basica vs Shared Memory')
        return
    N, VARIANT, _BLOCK, _CM, _CS, GMEAN = range(6)
    n_values = np.unique(gpu_cmp[:, N])
    width = 0.35
    x = np.arange(len(n_values))
    for i, variant in enumerate((0, 1)):
        means = []
        for n in n_values:
            mask = (gpu_cmp[:, N] == n) & (gpu_cmp[:, VARIANT] == variant)
            means.append(gpu_cmp[mask, GMEAN][0] if np.any(mask) else np.nan)
        ax.bar(x + (i - 0.5) * width, means, width,
               label=VARIANT_LABELS[variant], color=VARIANT_COLORS[variant])
    ax.set_xticks(x)
    ax.set_xticklabels([str(int(n)) for n in n_values])
    ax.set_xlabel('N (cuerpos)')
    ax.set_ylabel('Tiempo GPU end-to-end medio (s)')
    ax.set_title('Basica vs Shared Memory (end-to-end, blockDim.x=256)')
    ax.legend()


def main():
    blockdim = load_table('blockdim_study.dat')
    gpu_cmp = load_table('gpu_benchmark_results.dat')

    fig, axes = plt.subplots(2, 2, figsize=(14, 12))
    fig.suptitle('Benchmarks GPU - Simulador N-Body CUDA (Lab 2)', fontsize=16)

    plot_speedup_vs_n(axes[0, 0], gpu_cmp)
    plot_kernel_vs_end2end(axes[0, 1], blockdim)
    plot_time_vs_blockdim(axes[1, 0], blockdim)
    plot_basic_vs_shared(axes[1, 1], gpu_cmp)

    for ax in axes.flat:
        ax.grid(True, alpha=0.3)

    plt.tight_layout(rect=[0.0, 0.0, 1.0, 0.96])
    plt.savefig('gpu_performance_plots.png', dpi=150)
    plt.close()
    print("Graficos GPU generados en 'gpu_performance_plots.png'")


if __name__ == '__main__':
    main()
