#!/usr/bin/env python3
"""
Vivado/Vitis Build Script - Python equivalent of Makefile
========================================================

This script replaces the Makefile for building Vivado projects and generating
XSA files for the KV260 RPICamera to DisplayPort project.

Usage:
    python build_vivado_proj.py [parameters]

Parameters:
    --target <value>         Build target to execute (default: all)
        all: Build complete project (default, depends on DEV_FLOW)
        vivado: Create project and open Vivado GUI
        bit: Generate bitstream
        xsa_non_extensible: Generate non-extensible XSA (for vitis_standalone)
        xsa_extensible: Generate extensible XSA (for vitis_platform)
        bitbin: Generate bitbin file
        dtbo: Generate device tree overlay
        xclbin: Generate XCLBIN file
        xpfm: Generate Vitis platform (XPFM) from extensible XSA
        program: Program the FPGA
        clean: Clean all output directories
    
    --dev-flow <value>       Development flow (default: vitis_standalone)
        vivado: Only hardware workflow
            - Required: FPGA RTL/IP/constraints files
            - Output: Bit file (.bit)
        vitis_standalone: Vitis standalone workflow (no extensible kernels)
            - Required: FPGA RTL/IP/constraints files  
            - Intermediate: Bit file
            - Output: XSA file containing bitstream
        vivado_accelerator: Vivado accelerator workflow (xmutil/dfx-mgr, no extensible kernels)
            - Required: FPGA RTL/IP/constraints files
            - Intermediate: Non-extensible XSA file
            - Output: Bitbin file (.bitbin) and DTBO file (.dtbo)
        vitis_platform: Vitis platform workflow (xmutil/dfx-mgr, extensible kernels)
            - Required: FPGA RTL/IP/constraints files + kernels (Vivado IP and .xo)
            - Intermediate: Extensible XSA file
            - Output: Bitbin file (.xclbin), DTBO file (.dtbo), and JSON file
    
    --jobs <number>          Parallel jobs for synthesis/implementation (default: 4)
    --reuse <bool>           Reuse existing artifacts if they exist (default: False)
    --synth-strategy <value> Synthesis strategy (Vivado Synthesis Defaults if not specified)
    --impl-strategy <value>  Implementation strategy (Vivado Implementation Defaults if not specified)

Examples:
    python build_vivado_proj.py                                   # Build complete project (default: all, vitis_standalone flow)
    python build_vivado_proj.py --target vivado                   # Create project and open Vivado GUI
    python build_vivado_proj.py --target bit --jobs 8             # Generate bitstream with 8 parallel jobs
    python build_vivado_proj.py --synth-strategy Flow_PerfOptimized_high --impl-strategy Performance_Explore
    python build_vivado_proj.py --target bitbin --reuse True      # Generate bitbin only if .bit exists    
    python build_vivado_proj.py --target clean                    # Clean all output directories
    python build_vivado_proj.py --target all --dev-flow vivado    # Build with vivado development flow

Copyright (c) 2026 Juan Manuel Reina
"""

import os
import sys
import argparse
import subprocess
import shutil
import pathlib
import platform
from typing import List, Dict, Optional
import time

class VivadoBuilder:
    def __init__(self):
        # Project configuration
        self.PROJECT_NAME = "kv260_dpu"
        self.BD_TOP = "bd_top"
        self.FPGA_PART = "XCK26-SFVC784-2LV-C"
        self.BOARD_PART = "xilinx.com:kv260_som:part0:1.3"
        self.BOARD_CONNECTIONS = "som240_1_connector xilinx.com:kv260_carrier:som240_1_connector:1.3"
        self.SYN_NUM_JOBS = 12
        self.DEV_FLOW = "vitis_standalone"
        # Primary tool locations (keep only the two primary constants)
        # On Windows, Vivado binary could look like C:/AMD/2025.2/Vivado/bin/vivado.bat
        # On Linux, Vivado binary could look like /opt/Xilinx/Vivado/2025.2/bin/vivado    

        self.VIVADO_ROOT = "/home/juanma/Xilinx/2025.2/Vivado"
        self.VITIS_ROOT = "/home/juanma/Xilinx/2025.2/Vitis"

        # Detect environment and set paths
        self.script_path = pathlib.Path(__file__).resolve()
        self.workspace_path = self.script_path.parent.parent
        self.is_windows = platform.system() == "Windows"
        
        # Adjust tool extensions for Windows
        vivado_exe = "vivado.bat" if self.is_windows else "vivado"
        vitis_exe = "vitis.bat" if self.is_windows else "vitis"
        bootgen_exe = "bootgen.bat" if self.is_windows else "bootgen"
        dtc_exe = "dtc.bat" if self.is_windows else "dtc"
        v_exe = "v++.bat" if self.is_windows else "v++"
        xsct_exe = "xsct.bat" if self.is_windows else "xsct"
        
        self.VIVADO_PATH = f"{self.VIVADO_ROOT}/bin/{vivado_exe}"
        self.VITIS_PATH = f"{self.VITIS_ROOT}/bin/{vitis_exe}"
        self.BOOTGEN_PATH = f"{self.VIVADO_ROOT}/bin/{bootgen_exe}"
        self.DTC_PATH = f"{self.VITIS_ROOT}/bin/{dtc_exe}"
        self.V_PP_PATH = f"{self.VITIS_ROOT}/bin/{v_exe}"
        self.XSCT_PATH = f"{self.VITIS_ROOT}/bin/{xsct_exe}"
        self.REUSE = False
        
        # Strategies for synthesis and implementation
        self.SYNTH_STRATEGY = "Flow_AreaOptimized_high"
        self.IMPL_STRATEGY = "Area_Explore"
        
        # Convert to forward slashes for TCL compatibility
        self.workspace_path_str = str(self.workspace_path).replace('\\', '/')
        
        # Output directories
        self.artifacts_path = self.workspace_path / "output" / "artifacts"
        self.vivado_path = self.workspace_path / "output" / "vivado"
        self.dtbo_path = self.workspace_path / "output" / "dtbo"
        self.xpfm_path = self.workspace_path / "output" / "xpfm"
        
        # Source files
        self.src_path = self.workspace_path / "rtl"
        self.src_vhdl_files = [
            # self.src_path / "counter_wrapper.vhd",
            # self.src_path / "pwm.vhd"
        ]
        self.src_vhdl08_files = [
            # self.src_path / "utils_pkg.vhd"
        ]
        self.src_verilog_files = [
            # self.src_path / "counter.v"
        ]
        self.inc_verilog_files = [
            # self.src_path / "utils.v"
        ]
        
        # Constraints and IPs
        self.xdc_files = [self.workspace_path / "constraints" / "kv260.xdc"]
        self.ip_tcl_files = [self.workspace_path / "ips" / "platform.tcl"]
        
        # Platform and kernel files
        self.pfm_tcl_path = self.workspace_path / "common" / "pfm.tcl"
        self.kernel_name = "logic_ops_nn"
        self.kernel_src_path = self.workspace_path / "kernels"
        self.link_input_path = self.workspace_path / "kernels" / "logic_ops_hls" / "logic_ops_nn.xo"
        
        print(f"Workspace path: {self.workspace_path_str}")
        print(f"Development flow: {self.DEV_FLOW}")

    def create_directories(self):
        """Create all necessary output directories"""
        print("Creating output directories...")
        directories = [
            self.artifacts_path,
            self.vivado_path,
            self.dtbo_path,
            self.xpfm_path
        ]
        
        for directory in directories:
            directory.mkdir(parents=True, exist_ok=True)
            print(f"  Created: {directory}")

    def clean(self):
        """Clean all output directories"""
        print("Cleaning output directories...")
        directories = [
            self.artifacts_path,
            self.vivado_path,
            self.dtbo_path,
            self.xpfm_path
        ]
        
        for directory in directories:
            if directory.exists():
                try:
                    shutil.rmtree(directory)
                    print(f"  Removed: {directory}")
                except PermissionError as e:
                    print(f"  Permission error removing {directory}: {e}")
                    print(f"  Attempting to remove contents individually...")
                    try:
                        # Try to remove files individually
                        for item in directory.rglob("*"):
                            try:
                                if item.is_file():
                                    item.chmod(0o666)  # Remove read-only attribute
                                    item.unlink()
                                elif item.is_dir():
                                    shutil.rmtree(item)
                            except (PermissionError, OSError) as e2:
                                print(f"    Could not remove {item}: {e2}")
                        # Try to remove the directory again
                        try:
                            directory.rmdir()
                            print(f"  Removed: {directory}")
                        except OSError:
                            print(f"  Could not remove directory {directory} (may be empty or locked)")
                    except Exception as e2:
                        print(f"  Failed to clean {directory}: {e2}")
        
        # Clean Vivado temporary files in output directory
        output_dir = self.workspace_path / "output"
        if output_dir.exists():
            patterns = ["vivado*.jou", "vivado*.log", "dfx_runtime.txt"]
            for pattern in patterns:
                for file_path in output_dir.glob(pattern):
                    try:
                        file_path.unlink()
                        print(f"  Removed: {file_path}")
                    except PermissionError as e:
                        print(f"  Permission error removing {file_path}: {e}")

    def run_vitis_script(self, py_script: str, working_dir: Optional[pathlib.Path] = None) -> bool:
        """Run Vitis with a Python script"""
        # Convert path to native format on Windows
        vitis_path = self.VITIS_PATH.replace('/', '\\') if self.is_windows else self.VITIS_PATH
        cmd = [vitis_path, "-s", py_script]
        
        if working_dir:
            original_cwd = os.getcwd()
            os.chdir(working_dir)
        else:
            original_cwd = None
            
        try:
            print(f"Executing Vitis Python Script: {' '.join(cmd)}")
            result = subprocess.run(cmd, text=True)
            return result.returncode == 0
        except FileNotFoundError:
            print("Error: vitis command not found.")
            return False
        finally:
            if original_cwd:
                os.chdir(original_cwd)

    def run_vivado(self, tcl_script: str, working_dir: Optional[pathlib.Path] = None) -> bool:
        """Run Vivado with a TCL script"""
        # Convert path to native format on Windows
        vivado_path = self.VIVADO_PATH.replace('/', '\\') if self.is_windows else self.VIVADO_PATH
        cmd = [vivado_path, "-nojournal", "-nolog", "-mode", "batch", "-source", tcl_script]
        
        if working_dir:
            original_cwd = os.getcwd()
            os.chdir(working_dir)
            print(f"Running Vivado from: {working_dir}")
        else:
            original_cwd = None
        
        try:
            print(f"Executing: {' '.join(cmd)}")
            result = subprocess.run(cmd, text=True)
            
            if result.returncode != 0:
                print(f"Vivado failed with return code {result.returncode}")
                return False
            else:
                print("Vivado completed successfully")
                return True
                
        except FileNotFoundError:
            print("Error: vivado command not found. Make sure Vivado is installed and in PATH.")
            return False
        finally:
            if original_cwd:
                os.chdir(original_cwd)

    def create_project_tcl(self) -> str:
        """Generate TCL script for creating Vivado project"""
        tcl_content = []
        
        # Create project
        tcl_content.append(f"create_project -force -part {self.FPGA_PART} {self.PROJECT_NAME}")
        tcl_content.append(f"set_property board_part {self.BOARD_PART} [current_project]")
        tcl_content.append(f"set_property board_connections {{{self.BOARD_CONNECTIONS}}} [current_project]")
        
        # Add sources
        if self.src_vhdl_files:
            vhdl_files_str = " ".join([str(f).replace('\\', '/') for f in self.src_vhdl_files])
            tcl_content.append(f"read_vhdl {{{vhdl_files_str}}}")
        
        if self.src_vhdl08_files:
            vhdl08_files_str = " ".join([str(f).replace('\\', '/') for f in self.src_vhdl08_files])
            tcl_content.append(f"read_vhdl -vhdl2008 {{{vhdl08_files_str}}}")
        
        if self.src_verilog_files or self.inc_verilog_files:
            verilog_files = self.src_verilog_files + self.inc_verilog_files
            verilog_files_str = " ".join([str(f).replace('\\', '/') for f in verilog_files])
            tcl_content.append(f"read_verilog {{{verilog_files_str}}}")
        
        # Add constraints
        if self.xdc_files:
            xdc_files_str = " ".join([str(f).replace('\\', '/') for f in self.xdc_files])
            tcl_content.append(f"add_files -fileset constrs_1 {{{xdc_files_str}}}")
        
        # Add IP TCL files
        for ip_tcl in self.ip_tcl_files:
            tcl_content.append(f"source {ip_tcl.as_posix().replace('\\', '/')}")
        
        return "\n".join(tcl_content)

    def create_project(self) -> bool:
        """Create Vivado project"""
        xpr_file = self.vivado_path / f"{self.PROJECT_NAME}.xpr"
        if self.REUSE and xpr_file.exists():
            print(f"Reusing existing project: {xpr_file}")
            return True

        print("\n" + "="*60)
        print("Creating Vivado project...")
        print("="*60 + "\n")
        
        # Change to vivado directory
        original_cwd = os.getcwd()
        os.chdir(self.vivado_path)
        
        try:
            # Generate TCL script
            tcl_content = self.create_project_tcl()
            tcl_file = "create_project.tcl"
            
            with open(tcl_file, 'w') as f:
                f.write(tcl_content)
            
            print(f"Generated TCL script: {tcl_file}")
            
            # Run Vivado
            return self.run_vivado(tcl_file)
            
        finally:
            os.chdir(original_cwd)

    def open_vivado_gui(self) -> bool:
        """Open Vivado GUI with the project"""
        print("\nOpening Vivado GUI...")
        
        original_cwd = os.getcwd()
        os.chdir(self.vivado_path)
        
        try:
            xpr_file = self.vivado_path / f"{self.PROJECT_NAME}.xpr"
            if not xpr_file.exists():
                print(f"Error: Project file {xpr_file} not found. Create project first.")
                return False
            
            # Convert path to native format on Windows
            vivado_path = self.VIVADO_PATH.replace('/', '\\') if self.is_windows else self.VIVADO_PATH
            cmd = [vivado_path, str(xpr_file)]
            print(f"Executing: {' '.join(cmd)}")
            
            # For GUI, we don't want to capture output
            result = subprocess.run(cmd)
            return result.returncode == 0
            
        finally:
            os.chdir(original_cwd)

    def run_synthesis(self) -> bool:
        """Run synthesis"""
        # Check for synthesis checkpoint
        dcp_file = self.vivado_path / f"{self.PROJECT_NAME}.runs" / "synth_1" / f"{self.BD_TOP}_wrapper.dcp"
        if self.REUSE and dcp_file.exists():
            print(f"Reusing existing synthesis: {dcp_file}")
            return True

        print("\n" + "="*60)
        print("Running synthesis...")
        print(f"Synthesis Strategy: {self.SYNTH_STRATEGY}")
        print("="*60 + "\n")
        
        original_cwd = os.getcwd()
        os.chdir(self.vivado_path)
        
        try:
            tcl_content = []
            tcl_content.append(f"open_project {self.PROJECT_NAME}.xpr")
            tcl_content.append("reset_run synth_1")
            tcl_content.append(f"set_property strategy {{{self.SYNTH_STRATEGY}}} [get_runs synth_1]")
            tcl_content.append(f"launch_runs -jobs {self.SYN_NUM_JOBS} synth_1")
            tcl_content.append("wait_on_run synth_1")
            
            tcl_file = "run_synth.tcl"
            with open(tcl_file, 'w') as f:
                f.write("\n".join(tcl_content))
            
            return self.run_vivado(tcl_file)
            
        finally:
            os.chdir(original_cwd)

    def run_implementation(self) -> bool:
        """Run implementation"""
        # Check for implementation checkpoint
        dcp_file = self.vivado_path / f"{self.PROJECT_NAME}.runs" / "impl_1" / f"{self.BD_TOP}_wrapper_routed.dcp"
        if self.REUSE and dcp_file.exists():
            print(f"Reusing existing implementation: {dcp_file}")
            return True

        print("\n" + "="*60)
        print("Running implementation...")
        print(f"Implementation Strategy: {self.IMPL_STRATEGY}")
        print("="*60 + "\n")
        
        original_cwd = os.getcwd()
        os.chdir(self.vivado_path)
        
        try:
            tcl_content = []
            tcl_content.append(f"open_project {self.PROJECT_NAME}.xpr")
            tcl_content.append("reset_run impl_1")
            tcl_content.append(f"set_property strategy {{{self.IMPL_STRATEGY}}} [get_runs impl_1]")
            tcl_content.append(f"launch_runs -jobs {self.SYN_NUM_JOBS} impl_1")
            tcl_content.append("wait_on_run impl_1")
            tcl_content.append("open_run impl_1")
            tcl_content.append(f"report_utilization -file {self.PROJECT_NAME}_utilization.rpt")
            tcl_content.append(f"report_utilization -hierarchical -file {self.PROJECT_NAME}_utilization_hierarchical.rpt")
            
            tcl_file = "run_impl.tcl"
            with open(tcl_file, 'w') as f:
                f.write("\n".join(tcl_content))
            
            return self.run_vivado(tcl_file)
            
        finally:
            os.chdir(original_cwd)

    def check_timing(self) -> bool:
        """Check timing after implementation and return True if timing is met"""
        print("\n" + "="*60)
        print("Checking timing after implementation...")
        print("="*60 + "\n")
        
        original_cwd = os.getcwd()
        os.chdir(self.vivado_path)
        
        try:
            # Create TCL script to check timing
            tcl_content = [
                f"open_project {self.PROJECT_NAME}.xpr",
                "open_run impl_1",
                # Get the worst slack value directly from the timing paths
                "set wns [get_property SLACK [get_timing_paths -delay_type max]]",
                "if {$wns == \"\"} { set wns 0 }",
                "puts \"Worst Negative Slack (WNS): $wns\"",
                "if {$wns < 0} {",
                "  puts \"ERROR: Timing failed with WNS = $wns\"",
                "  exit 1",
                "} else {",
                "  puts \"SUCCESS: Timing met with WNS = $wns\"",
                "  exit 0",
                "}"
            ]
            
            tcl_file = "check_timing.tcl"
            with open(tcl_file, 'w') as f:
                f.write("\n".join(tcl_content))
            
            cmd = [self.VIVADO_PATH, "-nojournal", "-nolog", "-mode", "batch", "-source", tcl_file]
            
            result = subprocess.run(cmd, text=True)
            
            if result.returncode == 0:
                print("✓ Timing check passed - safe to generate bitstream")
                return True
            else:
                print("✗ Timing check FAILED - bitstream generation will be skipped")
                return False
                
        except Exception as e:
            print(f"Error during timing check: {e}")
            return False
        finally:
            os.chdir(original_cwd)

    def generate_bitstream(self) -> bool:
        """Generate bitstream"""
        bit_file = self.artifacts_path / f"{self.PROJECT_NAME}.bit"
        if self.REUSE and bit_file.exists():
            print(f"Reusing existing bitstream: {bit_file}")
            return True

        # Check timing before proceeding with bitstream generation
        if not self.check_timing():
            print("\n" + "="*60)
            print("BITSTREAM GENERATION BLOCKED: Timing constraints not met!")
            print("Please fix timing issues and re-run the build.")
            print("="*60 + "\n")
            return False

        print("\n" + "="*60)
        print("Generating bitstream...")
        print("="*60 + "\n")
            
        original_cwd = os.getcwd()
        os.chdir(self.vivado_path)
        
        try:
            # Remove existing bitstream to force regeneration
            bit_file = self.vivado_path / f"{self.PROJECT_NAME}.runs" / "impl_1" / f"{self.PROJECT_NAME}.bit"
            if bit_file.exists():
                bit_file.unlink()
            
            tcl_content = []
            tcl_content.append(f"open_project {self.PROJECT_NAME}.xpr")
            tcl_content.append("open_run impl_1")
            tcl_content.append(f"write_bitstream -force {self.PROJECT_NAME}.runs/impl_1/{self.PROJECT_NAME}.bit")
            tcl_content.append(f"write_debug_probes -force {self.PROJECT_NAME}.runs/impl_1/{self.PROJECT_NAME}.ltx")
            
            tcl_file = "generate_bit.tcl"
            with open(tcl_file, 'w') as f:
                f.write("\n".join(tcl_content))
            
            success = self.run_vivado(tcl_file)
            
            if success:
                # Create symbolic links/copy to artifacts directory
                bit_source = self.vivado_path / f"{self.PROJECT_NAME}.runs" / "impl_1" / f"{self.PROJECT_NAME}.bit"
                bit_dest = self.artifacts_path / f"{self.PROJECT_NAME}.bit"
                
                if bit_source.exists():
                    shutil.copy2(bit_source, bit_dest)
                    print(f"Copied bitstream to: {bit_dest}")
                
                # Copy LTX file if it exists
                ltx_source = self.vivado_path / f"{self.PROJECT_NAME}.runs" / "impl_1" / f"{self.PROJECT_NAME}.ltx"
                ltx_dest = self.artifacts_path / f"{self.PROJECT_NAME}.ltx"
                
                if ltx_source.exists():
                    shutil.copy2(ltx_source, ltx_dest)
                    print(f"Copied LTX file to: {ltx_dest}")
            
            return success
            
        finally:
            os.chdir(original_cwd)

    def generate_xsa_non_extensible(self) -> bool:
        """Generate non-extensible XSA file"""
        xsa_path = self.artifacts_path / f"{self.PROJECT_NAME}.xsa"
        if self.REUSE and xsa_path.exists():
            print(f"Reusing existing XSA: {xsa_path}")
            return True

        print("\n" + "="*60)
        print("Generating non-extensible XSA file...")
        print("="*60 + "\n")
        
        original_cwd = os.getcwd()
        os.chdir(self.vivado_path)
        
        try:
            # Copy bitstream with expected name
            bit_source = self.vivado_path / f"{self.PROJECT_NAME}.runs" / "impl_1" / f"{self.PROJECT_NAME}.bit"
            bit_dest = self.vivado_path / f"{self.PROJECT_NAME}.runs" / "impl_1" / f"{self.BD_TOP}_wrapper.bit"
            
            if bit_source.exists():
                shutil.copy2(bit_source, bit_dest)
            
            tcl_content = []
            tcl_content.append(f"open_project {self.PROJECT_NAME}.xpr")
            xsa_path = self.artifacts_path / f"{self.PROJECT_NAME}.xsa"
            tcl_content.append(f"write_hw_platform -fixed -include_bit -force -file {xsa_path.as_posix().replace('\\', '/')}")
            
            tcl_file = "generate_xsa.tcl"
            with open(tcl_file, 'w') as f:
                f.write("\n".join(tcl_content))
            
            success = self.run_vivado(tcl_file)
            
            if success and xsa_path.exists():
                print(f"Generated XSA: {xsa_path}")
                # Create marker file in vivado directory
                marker_file = self.vivado_path / "xsa_non_ext"
                marker_file.touch()
            
            return success
            
        finally:
            os.chdir(original_cwd)

    def generate_xsa_extensible(self) -> bool:
        """Generate extensible XSA file"""
        xsa_path = self.artifacts_path / f"{self.PROJECT_NAME}.xsa"
        if self.REUSE and xsa_path.exists():
            print(f"Reusing existing extensible XSA: {xsa_path}")
            return True

        print("\n" + "="*60)
        print("Generating extensible XSA file...")
        print("="*60 + "\n")
        
        original_cwd = os.getcwd()
        os.chdir(self.vivado_path)
        
        try:
            tcl_content = []
            tcl_content.append(f"open_project {self.PROJECT_NAME}.xpr")
            
            # Generate output products for block design
            tcl_content.append(f"delete_ip_run [get_files -of_objects [get_fileset sources_1] {self.PROJECT_NAME}.srcs/sources_1/bd/{self.BD_TOP}/{self.BD_TOP}.bd]")
            tcl_content.append(f"set_property synth_checkpoint_mode None [get_files {self.PROJECT_NAME}.srcs/sources_1/bd/{self.BD_TOP}/{self.BD_TOP}.bd]")
            tcl_content.append(f"generate_target all [get_files {self.PROJECT_NAME}.srcs/sources_1/bd/{self.BD_TOP}/{self.BD_TOP}.bd]")
            
            # Export IP user files
            tcl_content.append(f"export_ip_user_files -of_objects [get_files {self.PROJECT_NAME}.srcs/sources_1/bd/{self.BD_TOP}/{self.BD_TOP}.bd] -no_script -sync -force -quiet")
            tcl_content.append(f"export_simulation -of_objects [get_files {self.PROJECT_NAME}.srcs/sources_1/bd/{self.BD_TOP}/{self.BD_TOP}.bd] -directory {self.PROJECT_NAME}.ip_user_files/sim_scripts -ip_user_files_dir {self.PROJECT_NAME}.ip_user_files -ipstatic_source_dir {self.PROJECT_NAME}.ip_user_files/ipstatic -lib_map_path [list {{modelsim={self.PROJECT_NAME}.cache/compile_simlib/modelsim}} {{questa={self.PROJECT_NAME}.cache/compile_simlib/questa}} {{xcelium={self.PROJECT_NAME}.cache/compile_simlib/xcelium}} {{vcs={self.PROJECT_NAME}.cache/compile_simlib/vcs}} {{riviera={self.PROJECT_NAME}.cache/compile_simlib/riviera}}] -use_ip_compiled_libs -force -quiet")
            
            # Configure platform properties
            tcl_content.append("set_property platform.board_id {board} [current_project]")
            tcl_content.append("set_property platform.name {name} [current_project]")
            tcl_content.append(f"set_property pfm_name {{xilinx:board:name:0.0}} [get_files -all {{{self.PROJECT_NAME}.srcs/sources_1/bd/{self.BD_TOP}/{self.BD_TOP}.bd}}]")
            tcl_content.append("set_property platform.extensible {true} [current_project]")
            tcl_content.append("set_property platform.design_intent.embedded {true} [current_project]")
            tcl_content.append("set_property platform.design_intent.datacenter {false} [current_project]")
            tcl_content.append("set_property platform.design_intent.server_managed {false} [current_project]")
            tcl_content.append("set_property platform.design_intent.external_host {false} [current_project]")
            tcl_content.append("set_property platform.default_output_type {sd_card} [current_project]")
            tcl_content.append("set_property platform.uses_pr {false} [current_project]")
            
            # Write XSA
            xsa_path = self.artifacts_path / f"{self.PROJECT_NAME}.xsa"
            tcl_content.append(f"write_hw_platform -hw -force -file {xsa_path.as_posix().replace('\\', '/')}")
            
            tcl_file = "generate_xsa.tcl"
            with open(tcl_file, 'w') as f:
                f.write("\n".join(tcl_content))
            
            success = self.run_vivado(tcl_file)
            
            if success and xsa_path.exists():
                print(f"Generated extensible XSA: {xsa_path}")
                # Create marker file in vivado directory
                marker_file = self.vivado_path / "xsa_ext"
                marker_file.touch()
                # Copy HWH to artifacts (needed for PYNQ/DPU tools)
                hwh_source = (self.vivado_path / f"{self.PROJECT_NAME}.gen" / "sources_1"
                              / "bd" / self.BD_TOP / "hw_handoff" / f"{self.BD_TOP}.hwh")
                if hwh_source.exists():
                    hwh_dest = self.artifacts_path / f"{self.BD_TOP}.hwh"
                    shutil.copy2(hwh_source, hwh_dest)
                    print(f"Copied HWH to: {hwh_dest}")
            
            return success
            
        finally:
            os.chdir(original_cwd)

    def generate_bitbin(self) -> bool:
        """Generate bitbin file"""
        bitbin_file = self.artifacts_path / f"{self.PROJECT_NAME}.bitbin"
        if self.REUSE and bitbin_file.exists():
            print(f"Reusing existing bitbin: {bitbin_file}")
            return True

        print("\n" + "="*60)
        print("Generating bitbin file...")
        print("="*60 + "\n")
        
        bit_file = self.artifacts_path / f"{self.PROJECT_NAME}.bit"
        if not bit_file.exists():
            print(f"Error: Bit file {bit_file} not found. Generate bitstream first.")
            return False
        
        original_cwd = os.getcwd()
        os.chdir(self.artifacts_path)
        
        try:
            # Create BIF file
            bif_content = f"all:{{{self.PROJECT_NAME}.bit}}"
            with open("bootgen.bif", 'w') as f:
                f.write(bif_content)
            
            # Run bootgen
            bootgen_path = self.BOOTGEN_PATH.replace('/', '\\') if self.is_windows else self.BOOTGEN_PATH
            cmd = [bootgen_path, "-w", "-arch", "zynqmp", "-process_bitstream", "bin", "-image", "bootgen.bif"]
            print(f"Executing: {' '.join(cmd)}")
            
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode != 0:
                print(f"Bootgen failed: {result.stderr}")
                return False
            else:
                bitbin_file = self.artifacts_path / f"{self.PROJECT_NAME}.bitbin"
                print(f"Generated bitbin: {bitbin_file}")
                return True
                
        except FileNotFoundError:
            print("Error: bootgen command not found. Make sure Xilinx tools are installed and in PATH.")
            return False
        finally:
            os.chdir(original_cwd)

    def program_fpga(self) -> bool:
        """Program the FPGA"""
        print("\n" + "="*60)
        print("Programming FPGA...")
        print("="*60 + "\n")
        
        bit_file = self.artifacts_path / f"{self.PROJECT_NAME}.bit"
        if not bit_file.exists():
            print(f"Error: Bit file {bit_file} not found. Generate bitstream first.")
            return False
        
        original_cwd = os.getcwd()
        os.chdir(self.vivado_path)
        
        try:
            tcl_content = []
            tcl_content.append("open_hw_manager")
            tcl_content.append("connect_hw_server")
            tcl_content.append("open_hw_target")
            tcl_content.append("current_hw_device [lindex [get_hw_devices] 0]")
            tcl_content.append("refresh_hw_device -update_hw_probes false [current_hw_device]")
            tcl_content.append(f"set_property PROGRAM.FILE {{{bit_file.as_posix().replace('\\', '/')}}} [current_hw_device]")
            tcl_content.append("program_hw_devices [current_hw_device]")
            tcl_content.append("exit")
            
            tcl_file = "program.tcl"
            with open(tcl_file, 'w') as f:
                f.write("\n".join(tcl_content))
            
            return self.run_vivado(tcl_file)
            
        finally:
            os.chdir(original_cwd)

    def generate_dtbo(self) -> bool:
        """Generate Device Tree Overlay (DTBO)"""
        dtbo_out = self.artifacts_path / f"{self.PROJECT_NAME}.dtbo"
        if self.REUSE and dtbo_out.exists():
            print(f"Reusing existing DTBO: {dtbo_out}")
            return True

        print("\n" + "="*60)
        print("Generating DTBO...")
        print("="*60 + "\n")
        
        xsa_path = self.artifacts_path / f"{self.PROJECT_NAME}.xsa"
        if not xsa_path.exists():
            print("Error: XSA not found for DTBO generation.")
            return False
            
        original_cwd = os.getcwd()
        
        # If we are here, we NEED to generate the DTBO. 
        # To avoid version mismatch errors, we ensure the vitis workspace is clean (only if not reusing).
        vitis_ws = self.dtbo_path / "vitis_ws"
        if not self.REUSE and vitis_ws.exists():
            try:
                shutil.rmtree(vitis_ws)
            except (PermissionError, OSError):
                pass  # Continue if cleanup fails
        
        self.dtbo_path.mkdir(parents=True, exist_ok=True)
        os.chdir(self.dtbo_path)
        
        try:
            # 1. Generate Vitis Python script for Platform/DTB generation
            py_script_content = [
                "import vitis",
                "import os",
                "import shutil",
                f"workspace = '{vitis_ws.as_posix()}'",
                "os.makedirs(workspace, exist_ok=True)",
                "client = vitis.create_client()",
                "try:",
                "    client.set_workspace(workspace)",
                "except Exception:",
                "    client.dispose()",
                "    shutil.rmtree(os.path.join(workspace, '.vitis'), ignore_errors=True)",
                "    client = vitis.create_client()",
                "    client.set_workspace(workspace)",
                "",
                "platform_name = 'p'",  # Very short to avoid MAX_PATH
                "hw_design = '" + xsa_path.as_posix() + "'",
                "",
                "print(f'Creating platform component from {hw_design}...')",
                "platform = client.create_platform_component(",
                "    name=platform_name,",
                "    hw_design=hw_design,",
                "    os='linux',",
                "    cpu='psu_cortexa53_0',",
                "    domain_name='d',",
                "    generate_dtb=True",
                ")",
                "",
                "print('Adding overlay domain...')",
                "platform.add_domain(",
                "    cpu='psu_cortexa53_0',",
                "    os='linux',",
                "    name='ovl',",
                "    generate_dtb=True,",
                "    dt_overlay=True",
                ")",
                "",
                "print('Building platform (DTB/DTBO generation)...')",
                "try:",
                "    platform.build()",
                "except Exception as e:",
                "    print(f'Build warning/error: {e}')",
                "    print('Proceeding to check if DTSI/DTBO was generated anyway...')",
                "vitis.dispose()"
            ]
            
            py_script = "build_platform.py"
            with open(py_script, 'w') as f:
                f.write("\n".join(py_script_content))
            
            if not self.run_vitis_script(py_script):
                return False
                
            # 2. Locate the generated DTSI and prepare artifact for editing
            platform_dir = self.dtbo_path / "vitis_ws" / "p"
            found_dtsis = list(platform_dir.glob("**/pl.dtsi")) + list(platform_dir.glob("**/system-top.dtsi"))
            
            if not found_dtsis:
                print("Error: Could not find generated DTSI file.")
                return False
                
            src_dtsi = found_dtsis[0]
            dtsi_artifact = self.artifacts_path / f"{self.PROJECT_NAME}.dtsi"
            
            # Copy to artifacts immediately so user can edit a persistent file
            shutil.copy2(src_dtsi, dtsi_artifact)
            
            print("\n" + "*"*80)
            print(f" DEVICE TREE SOURCE READY FOR EDITING AT:")
            print(f" {dtsi_artifact}")
            print("*"*80)
            print(" ACTION REQUIRED:")
            print(" Open the file ABOVE in your editor (the one in artifacts), edit it as required and save it.")
            print("*"*80)
            input(" Press Enter once you have finished editing to continue with compilation...")
            
            # 3. Manually compile the artifact version
            print(f"Compiling edited DTSI from artifacts: {dtsi_artifact}")
            dtbo_out = self.artifacts_path / f"{self.PROJECT_NAME}.dtbo"
            dtc_path = self.DTC_PATH.replace('/', '\\') if self.is_windows else self.DTC_PATH
            cmd = [dtc_path, "-@", "-O", "dtb", "-o", str(dtbo_out), str(dtsi_artifact)]
            
            subprocess.run(cmd, check=True)
            print(f"Successfully generated manually edited DTBO at: {dtbo_out}")
                
            return True
            
        except Exception as e:
            print(f"DTBO generation failed: {e}")
            return False
        finally:
            os.chdir(original_cwd)

    def copy_shell_json(self) -> bool:
        """Copy shell.json to artifacts"""
        shell_src = self.workspace_path / "common" / "shell.json"
        shell_dest = self.artifacts_path / "shell.json"
        # Respect reuse flag: if artifact already exists, skip copying
        if self.REUSE and shell_dest.exists():
            print(f"Reusing existing shell.json at: {shell_dest}")
            return True
        if shell_src.exists():
            shutil.copy2(shell_src, shell_dest)
            print(f"Copied shell.json to {shell_dest}")
            return True
        return False

    def generate_xpfm(self) -> bool:
        """Generate Vitis platform (XPFM)"""
        xpfm_marker = self.xpfm_path / "platform_generated"
        if self.REUSE and xpfm_marker.exists():
            print(f"Reusing existing Vitis platform")
            return True

        print("\n" + "="*60)
        print("Generating Vitis platform (XPFM)...")
        print("="*60 + "\n")
        
        xsa_path = self.artifacts_path / f"{self.PROJECT_NAME}.xsa"
        if not xsa_path.exists():
            print(f"Error: XSA file {xsa_path} not found. Generate XSA first.")
            return False
        
        self.xpfm_path.mkdir(parents=True, exist_ok=True)
        
        # Clean up existing platform directory to avoid conflicts
        if self.xpfm_path.exists():
            try:
                shutil.rmtree(self.xpfm_path)
                print(f"Cleaned up existing platform directory: {self.xpfm_path}")
            except (PermissionError, OSError) as e:
                print(f"Error: Failed to remove {self.xpfm_path}: {e}")
                print("Cannot proceed with platform generation. Please manually remove the directory and retry.")
                return False
        
        # Recreate the directory after deletion
        self.xpfm_path.mkdir(parents=True, exist_ok=True)
        
        try:
            xsa_path_unix = xsa_path.as_posix().replace('\\', '/')

            # Write a TCL script instead of using -eval to avoid shell quoting issues on Windows
            tcl_content = "\n".join([
                f"platform create -name {self.PROJECT_NAME}_vitis_platform \\",
                f"    -hw {xsa_path_unix} \\",
                f"    -os linux \\",
                f"    -proc psu_cortexa53 \\",
                f"    -out [pwd]",
                "platform generate",
            ])
            tcl_file = self.xpfm_path / "create_platform.tcl"
            tcl_file.write_text(tcl_content)
            
            xsct_path = self.XSCT_PATH.replace('/', '\\') if self.is_windows else self.XSCT_PATH
            cmd = [xsct_path, str(tcl_file)]
            
            print(f"Executing: {' '.join(cmd)}")
            result = subprocess.run(cmd, cwd=str(self.xpfm_path), text=True)
            
            if result.returncode == 0:
                # Check if platform was actually created at the expected location
                expected_xpfm = self.xpfm_path / f"{self.PROJECT_NAME}_vitis_platform" / "export" / f"{self.PROJECT_NAME}_vitis_platform" / f"{self.PROJECT_NAME}_vitis_platform.xpfm"
                if expected_xpfm.exists():
                    xpfm_marker.touch()
                    print(f"Generated Vitis platform in: {self.xpfm_path}")
                    print(f"XPFM file: {expected_xpfm}")
                    return True
                else:
                    print(f"Error: xsct exited successfully but XPFM file not found at: {expected_xpfm}")
                    return False
            else:
                print(f"xsct failed with return code {result.returncode}")
                return False
                
        except FileNotFoundError:
            print("Error: xsct command not found. Make sure Xilinx tools are installed and in PATH.")
            return False

    def generate_xclbin(self) -> bool:
        """Link kernel .xo with the Vitis platform using v++ to produce an XCLBIN."""
        xclbin_dest = self.artifacts_path / f"{self.PROJECT_NAME}.xclbin"

        if self.REUSE and xclbin_dest.exists():
            print(f"Reusing existing xclbin: {xclbin_dest}")
            # Ensure the post-link HWH is also in artifacts (may have been missed on a previous run)
            hwh_dest = self.artifacts_path / f"{self.PROJECT_NAME}.hwh"
            if not hwh_dest.exists():
                post_link_hwh = (self.xpfm_path / "temp" / "link" / "vivado" / "vpl" / "prj"
                                 / "prj.gen" / "sources_1" / "bd" / self.BD_TOP
                                 / "hw_handoff" / f"{self.BD_TOP}.hwh")
                if post_link_hwh.exists():
                    shutil.copy2(post_link_hwh, hwh_dest)
                    print(f"Copied post-link HWH to: {hwh_dest}")
                else:
                    print(f"Warning: post-link HWH not found at {post_link_hwh}")
            return True

        print("\n" + "="*60)
        print("Generating XCLBIN (v++ link)...")
        print("="*60 + "\n")

        # XPFM path matches what generate_xpfm creates via xsct
        xpfm_file = (self.xpfm_path
                     / f"{self.PROJECT_NAME}_vitis_platform"
                     / "export"
                     / f"{self.PROJECT_NAME}_vitis_platform"
                     / f"{self.PROJECT_NAME}_vitis_platform.xpfm")
        if not xpfm_file.exists():
            print(f"Error: XPFM file not found at {xpfm_file}. Run xpfm target first.")
            return False

        if not self.link_input_path.exists():
            print(f"Error: Kernel XO file not found at {self.link_input_path}.")
            return False

        original_cwd = os.getcwd()
        os.chdir(self.xpfm_path)

        temp_dir = self.xpfm_path / "temp"
        temp_dir.mkdir(parents=True, exist_ok=True)
        xclbin_out = self.xpfm_path / f"{self.PROJECT_NAME}.xclbin"

        # v++ -l (link): no --kernel flag; kernels come from the .xo input files
        v_path = self.V_PP_PATH.replace('/', '\\') if self.is_windows else self.V_PP_PATH
        cmd = [
            v_path, "-l", "--save-temps", "-t", "hw",
            "--platform", xpfm_file.as_posix().replace('\\', '/'),
            "--temp_dir", str(temp_dir),
            "-o", str(xclbin_out),
            str(self.link_input_path)
        ]

        env = os.environ.copy()
        env["XILINX_VIVADO"] = self.VIVADO_ROOT

        try:
            print(f"Executing: {' '.join(cmd)}")
            result = subprocess.run(cmd, env=env)
            if result.returncode == 0:
                shutil.copy2(xclbin_out, xclbin_dest)
                print(f"Successfully generated {xclbin_dest}")

                # Copy the post-link HWH (contains kernel IPs) to artifacts so that
                # PYNQ can auto-discover IP instances (e.g. logic_ops_nn_1).
                # Named to match the xclbin so Overlay() finds it automatically.
                post_link_hwh = (temp_dir / "link" / "vivado" / "vpl" / "prj"
                                 / "prj.gen" / "sources_1" / "bd" / self.BD_TOP
                                 / "hw_handoff" / f"{self.BD_TOP}.hwh")
                if post_link_hwh.exists():
                    hwh_dest = self.artifacts_path / f"{self.PROJECT_NAME}.hwh"
                    shutil.copy2(post_link_hwh, hwh_dest)
                    print(f"Copied post-link HWH to: {hwh_dest}")
                else:
                    print(f"Warning: post-link HWH not found at {post_link_hwh}")

                return True
            print(f"v++ link failed with return code {result.returncode}")
            return False
        except FileNotFoundError:
            print("Error: v++ command not found. Make sure Vitis is installed and in PATH.")
            return False
        finally:
            os.chdir(original_cwd)

    def build_target(self, target: str, _directories_created: bool = False) -> bool:
        """Build a specific target"""
        print(f"Building target: {target}")
        
        if target == "clean":
            self.clean()
            return True
        
        # Create directories for all other targets (only once)
        if not _directories_created:
            self.create_directories()
        
        if target == "vivado":
            # Create project first, then open GUI
            if not self.create_project():
                return False
            return self.open_vivado_gui()
        
        elif target == "bit":
            # Create project, run synthesis, implementation, and generate bitstream
            if not self.create_project():
                return False
            if not self.run_synthesis():
                return False
            if not self.run_implementation():
                return False
            return self.generate_bitstream()

        elif target == "program":
            # Need bitstream first
            if not self.build_target("bit", _directories_created=True):
                return False
            return self.program_fpga()            
        
        elif target == "xsa_non_extensible":
            # Need bitstream first
            if not self.build_target("bit", _directories_created=True):
                return False
            return self.generate_xsa_non_extensible()
        
        elif target == "xsa_extensible":
            # Requires synthesis and implementation before write_hw_platform -hw
            if not self.create_project(): return False
            if not self.run_synthesis(): return False
            if not self.run_implementation(): return False
            return self.generate_xsa_extensible()
        
        elif target == "bitbin":
            # Need bitstream first
            if not self.build_target("bit", _directories_created=True):
                return False
            return self.generate_bitbin()

        elif target == "xpfm":
            # Need extensible XSA first
            if not self.build_target("xsa_extensible", _directories_created=True):
                return False
            return self.generate_xpfm()

        elif target == "xclbin":
            # Need extensible XSA first
            if not self.build_target("xpfm", _directories_created=True):
                return False
            return self.generate_xclbin()

        elif target == "dtbo":
            # Needs xclbin first
            if not self.build_target("xclbin", _directories_created=True):
                return False
            return self.generate_dtbo()
        
        elif target == "all":
            # Build based on development flow
            if self.DEV_FLOW == "vivado":
                return self.build_target("bit", _directories_created=True)
            elif self.DEV_FLOW == "vitis_standalone":
                return self.build_target("xsa_non_extensible", _directories_created=True)
            elif self.DEV_FLOW == "vivado_accelerator":
                if not self.build_target("bit", _directories_created=True): return False
                if not self.generate_bitbin(): return False
                if not self.generate_xsa_non_extensible(): return False
                if not self.generate_dtbo(): return False
                return self.copy_shell_json()
            elif self.DEV_FLOW == "vitis_platform":
                # Synth+impl needed before extensible XSA; bitstream is produced
                # by v++ link (inside the XCLBIN), not separately by Vivado.
                if not self.create_project(): return False
                if not self.run_synthesis(): return False
                if not self.run_implementation(): return False
                if not self.generate_xsa_extensible(): return False
                if not self.generate_xpfm(): return False
                if not self.generate_xclbin(): return False
                if not self.generate_dtbo(): return False
                return self.copy_shell_json()
            else:
                print(f"Error: Unsupported development flow: {self.DEV_FLOW}")
                return False
                        
        else:
            print(f"Error: Unknown target: {target}")
            return False

def main():
    parser = argparse.ArgumentParser(
        description="Vivado/Vitis Build Script - Python equivalent of Makefile",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    
    parser.add_argument(
        "--target",
        default="all",
        choices=["all", "vivado", "bit", "xsa_non_extensible", "xsa_extensible", 
                "bitbin", "dtbo", "xclbin", "xpfm", "program", "clean"],
        help="Build target to execute (default: all)"
    )
    
    parser.add_argument(
        "--dev-flow",
        choices=["vivado", "vitis_standalone", "vivado_accelerator", "vitis_platform"],
        default="vitis_standalone",
        help="Development flow (default: vitis_standalone)"
    )
    
    parser.add_argument(
        "--jobs",
        type=int,
        default=4,
        help="Number of parallel jobs for synthesis/implementation (default: 4)"
    )

    parser.add_argument(
        "--reuse",
        type=lambda x: (str(x).lower() in ['true', '1', 'yes']),
        default=False,
        help="Reuse existing artifacts if they exist (default: False)"
    )
    
    parser.add_argument(
        "--synth-strategy",
        default="Flow_AreaOptimized_high",
        choices=["Flow_AreaOptimized_high", "Flow_AreaOptimized_medium", "Flow_AreaOptimized_low",
                 "Flow_PerfOptimized_high", "Flow_PerfOptimized_medium", "Flow_RuntimeOptimized"],
        help="Synthesis strategy (default: Flow_AreaOptimized_high)"
    )
    
    parser.add_argument(
        "--impl-strategy",
        default="Area_Explore",
        choices=["Area_Explore", "Performance_Explore", "Performance_ExplorePostRoutePhysOpt",
                 "Congestion_SpreadLogic", "Default"],
        help="Implementation strategy (default: Area_Explore)"
    )
    
    args = parser.parse_args()
    
    # Create builder
    builder = VivadoBuilder()
    
    # Override settings from command line
    builder.DEV_FLOW = args.dev_flow
    builder.SYN_NUM_JOBS = args.jobs
    builder.REUSE = args.reuse
    builder.SYNTH_STRATEGY = args.synth_strategy
    builder.IMPL_STRATEGY = args.impl_strategy
    
    print(f"Python Vivado Builder")
    print(f"Target: {args.target}")
    print(f"Development Flow: {builder.DEV_FLOW}")
    print(f"Parallel Jobs: {builder.SYN_NUM_JOBS}")
    print(f"Synthesis Strategy: {builder.SYNTH_STRATEGY}")
    print(f"Implementation Strategy: {builder.IMPL_STRATEGY}")
    print(f"Reuse artifacts: {builder.REUSE}")
    print()
    
    # Build the target
    start_time = time.time()
    success = builder.build_target(args.target)
    end_time = time.time()
    
    print()
    print("="*60)
    if success:
        if args.target == "clean":
            print(f"CLEAN SUCCESSFUL - Completed in {end_time - start_time:.1f} seconds")
        else:
            print(f"BUILD SUCCESSFUL - Completed in {end_time - start_time:.1f} seconds")
    else:
        if args.target == "clean":
            print(f"CLEAN FAILED - Completed in {end_time - start_time:.1f} seconds")
        else:
            print(f"BUILD FAILED - Completed in {end_time - start_time:.1f} seconds")
    print("="*60)
    
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()
