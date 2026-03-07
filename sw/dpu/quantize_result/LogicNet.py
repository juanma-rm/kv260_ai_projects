# GENETARED BY NNDCT, DO NOT EDIT!

import torch
from torch import tensor
import pytorch_nndct as py_nndct

class LogicNet(py_nndct.nn.NndctQuantModel):
    def __init__(self):
        super(LogicNet, self).__init__()
        self.module_0 = py_nndct.nn.Input() #LogicNet::input_0(LogicNet::nndct_input_0)
        self.module_1 = py_nndct.nn.Linear(in_features=2, out_features=8, bias=True) #LogicNet::LogicNet/Sequential[net]/Linear[0]/ret.3(LogicNet::nndct_dense_1)
        self.module_2 = py_nndct.nn.ReLU(inplace=False) #LogicNet::LogicNet/Sequential[net]/ReLU[1]/ret.5(LogicNet::nndct_relu_2)
        self.module_3 = py_nndct.nn.Linear(in_features=8, out_features=3, bias=True) #LogicNet::LogicNet/Sequential[net]/Linear[2]/ret.7(LogicNet::nndct_dense_3)
        self.module_4 = py_nndct.nn.Sigmoid() #LogicNet::LogicNet/Sequential[net]/Sigmoid[3]/ret(LogicNet::nndct_sigmoid_4)

    @py_nndct.nn.forward_processor
    def forward(self, *args):
        output_module_0 = self.module_0(input=args[0])
        output_module_0 = self.module_1(output_module_0)
        output_module_0 = self.module_2(output_module_0)
        output_module_0 = self.module_3(output_module_0)
        output_module_0 = self.module_4(output_module_0)
        return output_module_0
