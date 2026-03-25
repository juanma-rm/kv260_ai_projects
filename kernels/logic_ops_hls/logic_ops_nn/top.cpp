#include "top.hpp"
#include <cmath>
#include "hls_math.h"

void input_scaler(nn_type_t input[INPUT_SIZE], nn_type_t output[INPUT_SIZE]) {
    input_scaler_loop: for (unsigned i = 0; i < INPUT_SIZE; i++) {
        #pragma HLS UNROLL
        output[i] = (input[i] - input_scaler_mean[i]) / input_scaler_scale[i];
    }
}

void layer1(nn_type_t input[INPUT_SIZE], nn_type_t output[HIDDEN_SIZE]) {
    #pragma HLS PIPELINE II=4

    layer1_loop: for (unsigned i = 0; i < HIDDEN_SIZE; i++) {
        output[i] = layer1_bias[i];
        for (unsigned j = 0; j < INPUT_SIZE; j++) {
            output[i] += layer1_weights[i][j] * input[j];
        }
        // ReLU activation
        output[i] = (output[i] > 0) ? output[i] : 0;
    }
}

void layer2(nn_type_t input[HIDDEN_SIZE], nn_type_t output[OUTPUT_SIZE]) {
    #pragma HLS PIPELINE II=4

    layer2_loop: for (unsigned i = 0; i < OUTPUT_SIZE; i++) {
        output[i] = layer2_bias[i];
        for (unsigned j = 0; j < HIDDEN_SIZE; j++) {
            output[i] += layer2_weights[i][j] * input[j];
        }
        // Sigmoid activation
        output[i] = 1.0f / (1.0f + hls::expf(-output[i]));
    }
}

void output(nn_type_t input[OUTPUT_SIZE], float* res_and, float* res_or, float* res_xor) {
    *res_and = input[0];
    *res_or = input[1];
    *res_xor = input[2];
}

void logic_ops_nn(const float a, const float b, float* res_and, float* res_or, float* res_xor) {
    #pragma HLS DATAFLOW
    #pragma HLS INTERFACE s_axilite port=a
    #pragma HLS INTERFACE s_axilite port=b
    #pragma HLS INTERFACE s_axilite port=res_and
    #pragma HLS INTERFACE s_axilite port=res_or
    #pragma HLS INTERFACE s_axilite port=res_xor
       
    // Prepare input (no need to do special type conversion, since nn_type_t = float)
    nn_type_t input[INPUT_SIZE] = {a, b};
    #pragma HLS ARRAY_PARTITION variable=input type=complete

    // Scale input
    nn_type_t scaled_input[INPUT_SIZE];
    #pragma HLS ARRAY_PARTITION variable=scaled_input type=complete
    input_scaler(input, scaled_input);

    // nn.Linear(2, 8) + nn.ReLU()
    nn_type_t layer1_output[HIDDEN_SIZE] = {0};
    #pragma HLS ARRAY_PARTITION variable=layer1_output type=complete
    layer1(scaled_input, layer1_output);

    // nn.Linear(8, 3) + nn.Sigmoid()
    nn_type_t layer2_output[OUTPUT_SIZE] = {0};
    #pragma HLS ARRAY_PARTITION variable=layer2_output type=complete
    layer2(layer1_output, layer2_output);

    // Output results (no need to do special type conversion, since nn_type_t = float)
    output(layer2_output, res_and, res_or, res_xor);

    return;

}