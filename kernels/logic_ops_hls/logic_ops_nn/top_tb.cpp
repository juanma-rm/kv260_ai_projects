#include <iostream>
#include <cassert>

void logic_ops_nn(const float a, const float b, float* res_and, float* res_or, float* res_xor);

int main () {

    float test_data[][2] = {
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

        float a = test_data[i][0];
        float b = test_data[i][1];
        float res_and, res_or, res_xor;
        logic_ops_nn(a, b, &res_and, &res_or, &res_xor);

        std::cout << "Input: (" << a << ", " << b << ") "
                  << "AND: " << res_and << " "
                  << "OR: " << res_or << " "
                  << "XOR: " << res_xor << std::endl;
        assert(((res_and > 0.5) == expected_and[i]) && "AND result does not match expected value");
        assert(((res_or > 0.5) == expected_or[i]) && "OR result does not match expected value");
        assert(((res_xor > 0.5) == expected_xor[i]) && "XOR result does not match expected value");
    }

    std::cout << "All tests passed!" << std::endl;

    return 0;
}