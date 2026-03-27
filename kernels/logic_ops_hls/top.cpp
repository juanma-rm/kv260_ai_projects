#include "top.hpp"
#include "hls_math.h"

void layer1(input_t input[INPUT_SIZE], layer1_act_t output[HIDDEN_SIZE]) {
    #pragma HLS PIPELINE II=4

    layer1_loop: for (unsigned i = 0; i < HIDDEN_SIZE; i++) {
        layer1_acc_t acc = layer1_bias[i];
        for (unsigned j = 0; j < INPUT_SIZE; j++) {
            acc += layer1_weights[i][j] * input[j];
        }
        // ReLU activation
        output[i] = (acc > 0) ? (layer1_act_t)acc : (layer1_act_t)0;
    }
}

void layer2(layer1_act_t input[HIDDEN_SIZE], layer2_act_t output[OUTPUT_SIZE]) {
    #pragma HLS PIPELINE II=4

    layer2_loop: for (unsigned i = 0; i < OUTPUT_SIZE; i++) {
        layer2_acc_t acc = layer2_bias[i];
        for (unsigned j = 0; j < HIDDEN_SIZE; j++) {
            acc += layer2_weights[i][j] * (layer2_weight_t)input[j];
        }
        // Sigmoid activation
        output[i] = (layer2_acc_t)((layer2_acc_t)1.0f / ((layer2_acc_t)1.0f + hls::exp(-acc)));
    }
}

void output(output_t input[OUTPUT_SIZE], output_t* res_and, output_t* res_or, output_t* res_xor) {
    *res_and = input[0];
    *res_or = input[1];
    *res_xor = input[2];
}

void logic_ops_nn(const input_t a, const input_t b, output_t* res_and, output_t* res_or, output_t* res_xor) {
    #pragma HLS DATAFLOW
    #pragma HLS INTERFACE s_axilite port=a
    #pragma HLS INTERFACE s_axilite port=b
    #pragma HLS INTERFACE s_axilite port=res_and
    #pragma HLS INTERFACE s_axilite port=res_or
    #pragma HLS INTERFACE s_axilite port=res_xor
       
    // Prepare input (it's already passed strictly as the quantized input)
    input_t input[INPUT_SIZE] = {a, b};
    #pragma HLS ARRAY_PARTITION variable=input type=complete

    // nn.Linear(2, 8) + nn.ReLU()
    layer1_act_t layer1_output[HIDDEN_SIZE];
    #pragma HLS ARRAY_PARTITION variable=layer1_output type=complete
    layer1(input, layer1_output);

    // nn.Linear(8, 3) 
    output_t layer2_output[OUTPUT_SIZE];
    #pragma HLS ARRAY_PARTITION variable=layer2_output type=complete
    layer2(layer1_output, layer2_output);

    // Output results directly in fixed point
    output(layer2_output, res_and, res_or, res_xor);

    return;

}