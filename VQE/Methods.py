from scipy.optimize import minimize
import numpy as np
import random
import matplotlib.pyplot as plt

from .Nucleus import Nucleus, TwoBodyExcitationOperator
from .Ansatze import UCCAnsatz, ADAPTAnsatz

class OptimizationConvergedException(Exception):
    pass

class UCCVQE():
    """Class to define the Variational Quantum Eigensolver (VQE) algorithm"""

    def __init__(self, Ansatz: UCCAnsatz, init_param: list[float], 
                 test_threshold: float = 1e-6, method: str = 'SLSQP') -> None:
        
        self.ansatz = Ansatz
        self.method = method
        self.parameters = init_param
        self.test_threshold = test_threshold
        self.fcalls = []
        self.energy = []
        self.rel_error = []
        self.final_parameters = []
        self.convergence = False

    
    def run(self) -> float:
        """Runs the VQE algorithm"""

        self.ansatz.fcalls = 0
        E0 = self.ansatz.energy(self.parameters)

        self.energy.append(E0)
        self.rel_error.append(abs((E0 - self.ansatz.nucleus.eig_val[0])/self.ansatz.nucleus.eig_val[0]))
        self.fcalls.append(self.ansatz.fcalls)
        self.ansatz.count_fcalls = True
        try:
            result = minimize(self.ansatz.energy, self.parameters, method=self.method, callback=self.callback)
        except OptimizationConvergedException:
            pass
        self.ansatz.count_fcalls = False
    
    def callback(self, params: list[float]) -> None:
        """Callback function to store the energy and parameters at each iteration
        and stop the optimization if the threshold is reached."""

        self.ansatz.count_fcalls = False
        E = self.ansatz.energy(params)
        self.ansatz.count_fcalls = True
        self.energy.append(E)
        self.rel_error.append(abs((E - self.ansatz.nucleus.eig_val[0])/self.ansatz.nucleus.eig_val[0]))
        self.fcalls.append(self.ansatz.fcalls)
        self.final_parameters = params
        if self.rel_error[-1] < self.test_threshold:
            self.convergence = True
            raise OptimizationConvergedException


class ADAPTVQE():

    def __init__(self, 
                 Ansatz: ADAPTAnsatz, 
                 test_threshold: float = 1e-6, 
                 method: str = 'SLSQP',
                 min_criterion: str = 'Repeated op',
                 tol: float = 1e-10,
                 return_data: bool = False) -> None:
        
        self.nucleus = Ansatz.nucleus
        self.ansatz = Ansatz
        self.test_threshold = test_threshold
        self.fcalls = []
        self.tot_operators=0
        self.tot_operators_layers=[]
        self.energy = []
        self.rel_error = []
        self.parameters = []
        self.convergence = False
        self.layer_fcalls = []
        self.tol = tol
        self.return_data = return_data

        try:
            self.method = method
        except method not in ['SLSQP', 'COBYLA','L-BFGS-B','BFGS']:
            print('Invalid optimization method')
            exit()

        try:
            self.min_criterion = min_criterion
        except min_criterion not in ['Repeated op', 'Gradient','None']:
            print('Invalid minimum criterion. Choose between "Repeated op", "Gradient" and "None"')
            exit()
    
    def run(self) -> tuple[list[TwoBodyExcitationOperator], list[float],list[float], 
                           list[float], list[float], list[int]]:
        """Runs the ADAPT VQE algorithm"""

        self.ansatz.fcalls = 0
        E0 = self.ansatz.energy(self.parameters)
        self.energy.append(E0)
        self.rel_error.append(abs((E0 - self.ansatz.nucleus.eig_val[0])/self.ansatz.nucleus.eig_val[0]))
        self.fcalls.append(self.ansatz.fcalls)
        self.tot_operators+=self.fcalls[-1]*len(self.ansatz.added_operators)
        self.tot_operators_layers.append(self.tot_operators)
        first_operator,first_gradient = self.ansatz.choose_operator()
        gradient_layers = [first_gradient]
        opt_grad_layers = []
        energy_layers = [E0]
        rel_error_layers = [self.rel_error[-1]]
        fcalls_layers = [self.fcalls[-1]]
        self.ansatz.added_operators.append(first_operator)
        while self.ansatz.minimum == False and len(self.ansatz.added_operators)<10:
            self.layer_fcalls.append(self.ansatz.fcalls)
            self.parameters.append(0.0)
            self.ansatz.count_fcalls = True
            try:
                result = minimize(self.ansatz.energy, self.parameters, method=self.method, callback=self.callback,tol=self.tol)
                self.parameters = list(result.x)
                if self.return_data:
                    if self.method!='COBYLA':
                        opt_grad= np.linalg.norm(result.jac)
                    else:
                        opt_grad=0
                    opt_grad_layers.append(opt_grad)
                self.ansatz.count_fcalls = False
                self.ansatz.ansatz = self.ansatz.build_ansatz(self.parameters)
                next_operator,next_gradient = self.ansatz.choose_operator()
                if self.min_criterion == 'Repeated op' and next_operator == self.ansatz.added_operators[-1]:
                    self.ansatz.minimum = True
                elif self.min_criterion == 'Gradient' and opt_grad < 1e-6:
                    self.ansatz.minimum = True
                else:
                    self.ansatz.added_operators.append(next_operator)
                    gradient_layers.append(next_gradient)
                    energy_layers.append(self.energy[-1])
                    rel_error_layers.append(self.rel_error[-1])
                    fcalls_layers.append(self.fcalls[-1])
            except OptimizationConvergedException:
                if self.return_data:
                    opt_grad_layers.append('Manually stopped')
        energy_layers.append(self.energy[-1])
        rel_error_layers.append(self.rel_error[-1])
        fcalls_layers.append(self.fcalls[-1])
        if self.min_criterion == 'None' and self.ansatz.minimum == False:
            self.ansatz.minimum = True
            opt_grad_layers.append('Manually stopped')
        if self.return_data:
            return  gradient_layers, opt_grad_layers, energy_layers, rel_error_layers, fcalls_layers
        
    def callback(self, params: list[float]) -> None:
        """Callback function to store the energy and parameters at each iteration
        and stop the optimization if the threshold is reached."""

        self.ansatz.count_fcalls = False
        E = self.ansatz.energy(params)
        self.ansatz.count_fcalls = True
        self.energy.append(E)
        self.rel_error.append(abs((E - self.ansatz.nucleus.eig_val[0])/self.ansatz.nucleus.eig_val[0]))
        self.fcalls.append(self.ansatz.fcalls)
        self.tot_operators+=(self.fcalls[-1]-self.fcalls[-2])*len(self.ansatz.added_operators)
        self.tot_operators_layers.append(self.tot_operators)
        if self.rel_error[-1] < self.test_threshold:
            self.convergence = True
            self.ansatz.minimum = True
            self.parameters = params
            raise OptimizationConvergedException



if __name__ == '__main__':
    Li6 = Nucleus('Li6', 1)
    ref_state = np.eye(Li6.d_H)[1]
    UCC_ansatz = UCCAnsatz(Li6, ref_state)
    vqe = UCCVQE(UCC_ansatz, np.zeros(len(UCC_ansatz.operators)))
    vqe.run()
    t_fin = vqe.final_parameters
    t0 = np.random.rand(len(t_fin))

    t3 = np.linspace(-7,7,1000)
    for n in range(len(t0)):
        E = [UCC_ansatz.lanscape(t_fin,t,n) for t in t3]
        plt.plot(t3,E)
        print(UCC_ansatz.lanscape(t_fin,0,n)-UCC_ansatz.lanscape(t_fin,2*np.pi,n))
    plt.show()
