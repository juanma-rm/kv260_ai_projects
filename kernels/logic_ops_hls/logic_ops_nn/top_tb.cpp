#include <iostream>
#include <cassert>
#include "top.hpp"

void logic_ops_nn(const input_t a, const input_t b, output_t* res_and, output_t* res_or, output_t* res_xor);

int main () {

    input_t test_data[][2] = {
        {0.0, 0.0},
        {0.0, 1.0},
        {1.0, 0.0},
        {1.0, 1.0}
    };

    bool expected_and[] = {0, 0, 0, 1};
    bool expected_or[] = {0, 1, 1, 1};
    bool expected_xor[] = {0, 1, 1, 0};

    unsigned num_samples = sizeof(test_data) / sizeof(test_data[0]);

    for (unsigned i = 0; i < num_samples; i++) {

        input_t a = test_data[i][0];
        input_t b = test_data[i][1];
        output_t res_and, res_or, res_xor;
        logic_ops_nn(a, b, &res_and, &res_or, &res_xor);

        // Cast to float specifically for clean stdout debug formatting
        float f_a = (float)a;
        float f_b = (float)b;
        float f_and = (float)res_and;
        float f_or  = (float)res_or;
        float f_xor = (float)res_xor;

        std::cout << "Input: (" << f_a << ", " << f_b << ") "
                  << "AND: " << f_and << " "
                  << "OR: " << f_or << " "
                  << "XOR: " << f_xor << std::endl;
        assert(((f_and > 0.5f) == expected_and[i]) && "AND result does not match expected value");
        assert(((f_or > 0.5f) == expected_or[i]) && "OR result does not match expected value");
        assert(((f_xor > 0.5f) == expected_xor[i]) && "XOR result does not match expected value");
    }

    std::cout << "All tests passed!" << std::endl;

    return 0;
}