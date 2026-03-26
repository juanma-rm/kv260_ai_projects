#ifndef TOP_HPP
#define TOP_HPP

#include "ap_fixed.h"

// Layer sizes
constexpr unsigned INPUT_SIZE = 2;
constexpr unsigned HIDDEN_SIZE = 8;
constexpr unsigned OUTPUT_SIZE = 3;

// Toggle for Float vs Fixed-point (quantized)
// #define USE_FLOAT

#ifdef USE_FLOAT
typedef float layer1_weight_t;
typedef float layer1_bias_t;
typedef float layer2_weight_t;
typedef float layer2_bias_t;
typedef float layer1_acc_t;
typedef float layer1_act_t;
typedef float layer2_acc_t;
typedef float layer2_act_t;
#else
// Type definitions. ap_fixed<total_bits, integer_bits>
typedef ap_fixed<8, 5> layer1_weight_t;
typedef ap_fixed<8, 4> layer1_bias_t;
typedef ap_fixed<8, 5> layer2_weight_t;
typedef ap_fixed<8, 6> layer2_bias_t;

// Intermediate types (wider to prevent overflow)
typedef ap_fixed<17, 11> layer1_acc_t;
typedef ap_fixed<17, 11> layer1_act_t;
typedef ap_fixed<28, 19> layer2_acc_t;
typedef ap_fixed<8, 2> layer2_act_t;
#endif

typedef layer1_weight_t input_t;
typedef layer2_act_t output_t;

// Weights and biases
#ifdef USE_FLOAT
const layer1_weight_t layer1_weights[HIDDEN_SIZE][INPUT_SIZE] = {
    {-3.900935, 0.054737}, {4.105870, 7.455179}, {0.512199, 7.130964}, {4.917362, 1.280722},
    {0.301381, -0.104492}, {3.759112, 2.670950}, {-5.668539, 5.973025}, {-0.826728, 0.299239}
};
const layer1_bias_t layer1_bias[HIDDEN_SIZE] = {
    3.638861, -4.105884, -1.902494, 0.001019, -0.644764, -2.185897, -0.197970, -0.858839
};
const layer2_weight_t layer2_weights[OUTPUT_SIZE][HIDDEN_SIZE] = {
    {-6.515682, 2.445804, 6.064849, -3.901655, -0.323450, 4.782142, -5.238679, 1.455613},
    {-4.061453, 8.128866, 5.505801, 1.016547, 0.303024, 10.259194, 1.615768, 3.316796},
    {-3.921119, -3.344274, -2.114886, 3.047232, -0.076883, 0.441659, 8.768048, -0.211050}
};
const layer2_bias_t layer2_bias[OUTPUT_SIZE] = {-13.796010, -3.294059, -0.805205};
#else
const layer1_weight_t layer1_weights[HIDDEN_SIZE][INPUT_SIZE] = {
    {-3.875,  0.0}, { 4.125,  7.5}, { 0.5,    7.125}, { 4.875,  1.25},
    { 0.25,  -0.125}, { 3.75,   2.625}, {-5.625,  6.0}, {-0.875,  0.25}
};
const layer1_bias_t layer1_bias[HIDDEN_SIZE] = {3.625, -4.125, -1.875, 0.0, -0.625, -2.1875, -0.1875, -0.875};
const layer2_weight_t layer2_weights[OUTPUT_SIZE][HIDDEN_SIZE] = {
    {-6.5,   2.5,   6.125, -3.875, -0.375,  4.75,  -5.25,  1.5},
    {-4.0,   8.125, 5.5,   1.0,    0.25,   10.25,   1.625,  3.375},
    {-3.875,-3.375,-2.125,  3.0,  -0.125,   0.5,    8.75,  -0.25}
};
const layer2_bias_t layer2_bias[OUTPUT_SIZE] = {-13.75, -3.25, -0.75};
#endif

#endif // TOP_HPP