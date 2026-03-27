# ===========================================================================
# Vitis HLS automation: logic_ops_nn kernel targeting KV260
#
# Runs the full flow: C simulation → Synthesis → Co-simulation → XO export
# 
# With Vitis 2025.2, use:
#   vitis-run --mode hls --tcl --input_file run_hls.tcl              # all
#   vitis-run --mode hls --tcl --input_file run_hls.tcl csim         # c sim
#   vitis-run --mode hls --tcl --input_file run_hls.tcl synth        # synth
#   vitis-run --mode hls --tcl --input_file run_hls.tcl cosim        # cosim
#   vitis-run --mode hls --tcl --input_file run_hls.tcl export       # export
#
# If tests fail in simulation/co-sim, the flow stops with a clear error.
# ===========================================================================

set project_name "logic_ops_nn"
set top_function "logic_ops_nn"
set part         "xck26-sfvc784-2LV-c"
set clock_period 4
set src_dir      [file dirname [info script]]

# ---------------------------------------------------------------------------
# Parse optional stage argument (default: run all)
# vitis-run may inject its own flags into $::argv, so we scan for
# a known stage name rather than blindly taking the first arg.
# ---------------------------------------------------------------------------
set valid_stages {all csim synth cosim export}
set stage "all"
foreach arg $::argv {
    if { [lsearch -exact $valid_stages $arg] != -1 } {
        set stage $arg
        break
    }
}

puts "============================================================"
puts " Stage: $stage | Part: $part | Clock: ${clock_period} ns"
puts "============================================================"

# ---------------------------------------------------------------------------
# Create / open project
# ---------------------------------------------------------------------------
open_project -reset $project_name

set_top $top_function
add_files      ${src_dir}/top.cpp
add_files      ${src_dir}/top.hpp
add_files -tb  ${src_dir}/top_tb.cpp

open_solution -reset "sol1" -flow_target vitis
set_part $part
create_clock -period $clock_period -name default

# ---------------------------------------------------------------------------
# Helper: Check for test pass patterns in output
# ---------------------------------------------------------------------------
proc verify_test_success {stage_name} {
    # The testbench prints "All tests passed!" on success.
    # If it doesn't, the HLS command will typically error out, which
    # we catch below. This is a safety check for clarity.
    puts "  → Waiting for test completion..."
}

proc run_sim_stage {stage_cmd stage_name} {
    global project_name
    puts "\n>>> Running $stage_name..."
    
    # Run the HLS command; if tests fail, it will error out
    if {[catch {eval $stage_cmd} err]} {
        puts "\n============================================================"
        puts " ❌ ERROR: $stage_name FAILED"
        puts "============================================================"
        puts "\nDetails: $err"
        puts "\nCheck the log files in: $project_name/sol1/"
        puts "============================================================\n"
        exit 1
    }
    
    puts "✓ $stage_name complete and tests PASSED."
}

# ---------------------------------------------------------------------------
# C Simulation
# ---------------------------------------------------------------------------
if { $stage eq "all" || $stage eq "csim" } {
    run_sim_stage "csim_design" "C Simulation"
}

# ---------------------------------------------------------------------------
# Synthesis
# ---------------------------------------------------------------------------
if { $stage eq "all" || $stage eq "synth" } {
    puts "\n>>> Running Synthesis..."
    csynth_design
    puts ">>> Synthesis complete."
}

# ---------------------------------------------------------------------------
# Co-Simulation
# ---------------------------------------------------------------------------
if { $stage eq "all" || $stage eq "cosim" } {
    run_sim_stage "cosim_design" "Co-Simulation"
}

# ---------------------------------------------------------------------------
# Export XO (Vitis kernel object)
# ---------------------------------------------------------------------------
if { $stage eq "all" || $stage eq "export" } {
    puts "\n>>> Exporting Vitis kernel object (.xo)..."
    export_design -format xo -output ${src_dir}/${project_name}.xo
    puts ">>> Export complete: ${src_dir}/${project_name}.xo"
}

puts "\n============================================================"
puts " ✓ All stages completed successfully!"
puts "   ($stage)"
puts "============================================================"
exit
