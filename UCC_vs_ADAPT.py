import numpy as np
from scipy import optimize
from tqdm import tqdm
from time import perf_counter
import matplotlib.pyplot as plt
import random
import os
from tqdm import tqdm
import pandas as pd

from VQE.Nucleus import Nucleus
from VQE.Ansatze import UCCAnsatz, ADAPTAnsatz
from VQE.Utils import labels_all_combinations
from VQE.Methods import UCCVQE, OptimizationConvergedException, ADAPTVQE


params = {'axes.linewidth': 1.4,
         'axes.labelsize': 16,
         'axes.titlesize': 18,
         'axes.linewidth': 1.5,
         'lines.markeredgecolor': "black",
     	'lines.linewidth': 1.5,
         'xtick.labelsize': 11,
         'ytick.labelsize': 14,
         "text.usetex": True,
         "font.family": "serif",
         "font.serif": ["Palatino"]
         }
plt.rcParams.update(params)


def UCC_vs_ADAPT(nuc: str, n_v: int, method: str = 'SLSQP', max_layers: int = 100) -> None:
    nucleus = Nucleus(nuc, 1)
    ref_state = np.eye(nucleus.d_H)[n_v]
    
    ADAPT_ansatz = ADAPTAnsatz(nucleus, ref_state, pool_format='Reduced')
    ADAPT_vqe = ADAPTVQE(ADAPT_ansatz, method = method, max_layers=max_layers)
    ADAPT_vqe.run()
    adapt_rel_error = ADAPT_vqe.rel_error
    adapt_energy = ADAPT_vqe.energy
    adapt_fcalls = ADAPT_vqe.fcalls

    print('ADAPT DONE')

    UCC_ansatz = UCCAnsatz(nucleus, ref_state, pool_format= 'Reduced')
    init_param = np.zeros(len(UCC_ansatz.operator_pool))
    UCC_vqe = UCCVQE(UCC_ansatz,init_param=init_param, method=method, max_layers=max_layers)
    UCC_vqe.run()
    ucc_rel_error = UCC_vqe.rel_error
    ucc_fcalls = UCC_vqe.fcalls

    plt.plot(adapt_fcalls, adapt_rel_error, label='ADAPT-VQE')
    plt.plot(ucc_fcalls, ucc_rel_error, label='UCC-VQE')
    plt.vlines(ADAPT_vqe.layer_fcalls, colors='lightgrey',ymin=1e-8,ymax=10, linestyles='dashed')
    plt.ylim((min([adapt_rel_error[-1],ucc_rel_error[-1]])*0.1), 10)
    plt.xlim(0, (max([ucc_fcalls[-1],adapt_fcalls[-1]])+30))
    plt.yscale('log')
    plt.xlabel('Function calls')
    plt.ylabel('Relative error')
    plt.legend()
    plt.title(f'UCC vs ADAPT-VQE (v{n_v})')

    plt.show()


def UCC_v_performance(method: str,
                      n_times: int = 1000,
                      ftol: float = 1e-7,
                      gtol: float = 1e-3,
                      rhoend: float = 1e-5,
                      test_threshold: float = 1e-6,
                      stop_at_threshold: bool = True,
                      pool_format: str = 'Only acting') -> None:
    Li6 = Nucleus('Li6', 1)
    vecs = np.eye(Li6.d_H)

    try:
        os.makedirs('outputs/v_performance/UCC')
    except OSError:
        pass
    output_folder = os.path.join('outputs/v_performance/UCC')


    file = open(os.path.join(output_folder, f'{method}_performance_randomt0_ntimes={n_times}_pool={pool_format}.dat'), 'w')
    for n_v,v in enumerate(vecs):
        print(f'{n_v}')
        ref_state = v
        UCC_ansatz = UCCAnsatz(Li6, ref_state = ref_state, pool_format = pool_format)

        calls = 0
        calls2 = 0
        n_fails = 0
        for n in tqdm(range(n_times)):
            init_param = np.random.uniform(low=-np.pi, high=np.pi,size=len(UCC_ansatz.operator_pool))
            random.shuffle(UCC_ansatz.operator_pool)
            vqe = UCCVQE(UCC_ansatz,
                         init_param=init_param,
                         method=method,
                         ftol = ftol,
                         gtol = gtol,
                         rhoend = rhoend,
                         test_threshold = test_threshold,
                         stop_at_threshold = stop_at_threshold)
            vqe.run()
            if vqe.success:
                calls += vqe.fcalls[-1]
                calls2 += vqe.fcalls[-1]**2
            else:
                n_fails += 1
        mean_calls = calls/(n_times-n_fails)
        std_calls = np.sqrt(calls2/(n_times-n_fails) - mean_calls**2)
        file.write(f'v{n_v}'+'\t'+f'{mean_calls}'+'\t'+f'{std_calls}'+'\t'+f'{n_fails}'+'\n')
    file.close()




if __name__ == '__main__':
    Li6 = Nucleus('Li6',1)
    He8 = Nucleus('He8',1)
    Be10= Nucleus('Be10',1)

    Li6_ansatz = UCCAnsatz(Li6,ref_state=np.eye(Li6.d_H)[1],pool_format='Reduced')
    He8_ansatz = UCCAnsatz(He8,ref_state=np.eye(He8.d_H)[0],pool_format='Reduced')
    Be10_ansatz = UCCAnsatz(Be10,ref_state=np.eye(Be10.d_H)[0],pool_format='Reduced')

    print('Li6',len(Li6_ansatz.operator_pool))
    print('He8',len(He8_ansatz.operator_pool))
    print('Be10',len(Be10_ansatz.operator_pool))