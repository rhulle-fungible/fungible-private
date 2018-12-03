from lib.system.fun_test import *
from lib.system import utils
from lib.topology.topology_helper import TopologyHelper
from lib.topology.dut import Dut, DutInterface
from lib.fun.f1 import F1
from lib.templates.storage.qemu_storage_template import QemuStorageTemplate
from lib.orchestration.simulation_orchestrator import DockerContainerOrchestrator
import re

'''
Script Write and Read in specific block in an extent of BLT Volume 
'''

topology_dict = {
    "name": "Basic Storage",
    "dut_info": {
        0: {
            "mode": Dut.MODE_SIMULATION,
            "type": Dut.DUT_TYPE_FSU,
            "interface_info": {
                0: {
                    "vms": 1,
                    "type": DutInterface.INTERFACE_TYPE_PCIE,
                    "vm_start_mode": "VM_START_MODE_NORMAL",
                    "vm_host_os": "fungible_yocto"
                }
            },
            "start_mode": F1.START_MODE_NORMAL
        }
    }
}


class BLTF1RestartQemuScript(FunTestScript):
    def describe(self):
        self.set_test_details(steps="""
        1. Deploy the topology. i.e Start 1 POSIXs and allocate a Linux instance 
        2. Make the Linux instance available for the testcase
        """)

    def setup(self):
        topology_obj_helper = TopologyHelper(spec=topology_dict)
        topology = topology_obj_helper.deploy()
        fun_test.test_assert(topology, "Ensure deploy is successful")
        fun_test.shared_variables["topology"] = topology

    def cleanup(self):
        # TopologyHelper(spec=fun_test.shared_variables["topology"]).cleanup()
        pass


class BLTF1RestartQemuTestcase(FunTestCase):

    def describe(self):
        pass

    def setup_blt_volume(self):
        """
        Create BLT volume using nvme commands
        :return:
        """
        # create namespace / BLT volume of 1GB (2 extents)
        cmd2 = self.qemu.host.command("/usr/local/sbin/nvme create-ns --nsze=262144 --ncap=262144 /dev/nvme0")
        fun_test.log("Namespace is created {}".format(cmd2))
        fun_test.simple_assert("Success" in cmd2, "Namespace is created")

        # attach namespace
        cmd3 = self.qemu.host.command("nvme attach-ns --namespace-id=1 --controllers=1 /dev/nvme0")
        fun_test.log("Namespace is attached {}".format(cmd3))

        # fun_test.add_checkpoint("BLT volume is created", "PASSED", True, command_result["status"])

        # Rebooting the qemu host before checking the disk as a workaround to the bug swos-1331
        if self.reboot_after_config:
            fun_test.simple_assert(self.qemu.reboot(timeout=self.command_timeout, retries=12), "Qemu Host Rebooted")
            self.need_dpc_server_start = True

        # Checking that the volume is accessible to the host
        lsblk_output = self.host.lsblk()
        fun_test.test_assert(self.volume_name in lsblk_output, "{} device available".format(self.volume_name))
        fun_test.test_assert_expected("disk", lsblk_output[self.volume_name]["type"],
                                      "{} device type check".format(self.volume_name))

    def f1_restart(self):
        f1_restart = self.qemu.start_dpc_server()
        fun_test.sleep("Waiting for the DPC server and DPCSH TCP proxy to settle down", self.iter_interval)
        fun_test.test_assert_expected(True, f1_restart, "F1 is restarted")

        return f1_restart


    def cleanup_blt_volume(self):
        pass

    def setup(self):

        testcase = self.__class__.__name__
        self.need_dpc_server_start = True

        # Parse configuration file
        config_file = fun_test.get_script_name_without_ext() + ".json"
        fun_test.log("Benchmark file being used: {}".format(config_file))
        benchmark_dict = utils.parse_file_to_json(config_file)

        for k, v in benchmark_dict[testcase].iteritems():
            setattr(self, k, v)
        # End of Config json file parsing

        self.topology = fun_test.shared_variables["topology"]
        self.dut = self.topology.get_dut_instance(index=0)
        fun_test.test_assert(self.dut, "Retrieved dut instance 0")
        self.host = self.topology.get_host_instance(dut_index=0, interface_index=0, host_index=0)
        self.qemu = QemuStorageTemplate(host=self.host, dut=self.dut)
        self.funos_running = True

        # Preserving the funos-posix and qemu commandline
        self.funos_cmdline = self.qemu.get_process_cmdline(F1.FUN_OS_SIMULATION_PROCESS_NAME)
        fun_test.log("\nfunos-posix commandline: {}".format(self.funos_cmdline))
        self.qemu_cmdline = self.qemu.get_process_cmdline(DockerContainerOrchestrator.QEMU_PROCESS)
        fun_test.log("\nQemu commandline: {}".format(self.qemu_cmdline))
        self.qemu_cmdline = re.sub(r'(.*append)\s+(root.*mem=\d+M)(.*)', r'\1 "\2"\3', self.qemu_cmdline)
        fun_test.log("\nProcessed Qemu commandline: {}".format(self.qemu_cmdline))

        # Starting the dpc server in the qemu host
        if self.need_dpc_server_start:
            self.f1_restart()
            # self.qemu.start_dpc_server()
            # fun_test.sleep("Waiting for the DPC server and DPCSH TCP proxy to settle down", self.iter_interval)
            # self.need_dpc_server_start = False

        self.volume_name = self.nvme_device.replace("/dev/", "") + "n" + str(self.ns_id)
        self.nvme_block_device = self.nvme_device + "n" + str(self.ns_id)
        self.volume_attached = False

    def write_test(self, start_block):
        """
        Function to write 8KB of data which will span across two subextent
        4KB on last block of subextent and remaining 4k on first block of subextent
        Repeat for extent
        """
        self.input_size = self.dd_block_size * self.dd_count
        return_size = self.qemu.dd(input_file=self.data_pattern, output_file=self.input_data,
                                   block_size=self.dd_block_size, count=self.dd_count)
        fun_test.test_assert_expected(self.input_size, return_size, "Input data creation")
        self.input_md5sum = self.qemu.md5sum(file_name=self.input_data)
        fun_test.simple_assert(self.input_md5sum, "Finding md5sum for input data")

        # Writing in two blocks
        self.nvme_count = self.dd_count

        write_result = self.qemu.nvme_write(device=self.nvme_block_device, start=start_block,
                                            count=self.nvme_count, size=self.input_size, data=self.input_data)

        write_return = False
        if write_result != "Success":
            self.write_result = False
            write_return = False
            fun_test.critical("Write failed")
        else:
            fun_test.log("Write succeeded")
            write_return = True

        return write_return

        # TODO: Code to validate two sub-extents are consumed for this write

    def read_test(self, start_block):
        """
        Read the data written
        :param start_block:
        :return:
        """
        # num_reads = self.dataset_size / self.input_size
        read_result = self.qemu.nvme_read(device=self.nvme_block_device, start=start_block,
                                          count=self.nvme_count, size=self.input_size, data=self.output_data)

        reat_return = False
        if read_result != "Success":
            self.read_result = False
            read_return = False
            fun_test.critical("Read failed")
        else:
            fun_test.log("Read succeeded ")

            output_md5sum = self.qemu.md5sum(file_name=self.output_data)
            if output_md5sum == self.input_md5sum:
                fun_test.log("md5sum for read {} matches with write md5sum {}".format(output_md5sum, self.input_md5sum))
                read_return = True
            else:
                self.read_result = False
                fun_test.critical("md5sum for {} is not matching with input md5sum {}".
                                  format(output_md5sum, self.input_md5sum))
                read_return = False

        return read_return

    def run(self):
        pass

    def cleanup(self):
        self.qemu.stop_dpc_server()


class BLTF1RestartQemu(BLTF1RestartQemuTestcase):

    def describe(self):
        self.set_test_details(id=1,
                              summary="Data verification after F1 restart with Qemu deployment",
                              steps="""
        1. Create BLT volume of 1GB using nvme create-ns
        2. Attach volume using nvme attach-ns
        3. Using nvme write, Write 4KB of data with specific start block
        4. Using nvme read, Read 4KB data starting from same block
        5. Verify md5sum of input and output is same
        6. Restart F1
        7. Read the blocks and verify output is same
        """)

    def setup(self):
        super(BLTF1RestartQemu, self).setup()

    def run(self):

        testcase = self.__class__.__name__
        self.setup_blt_volume()

        """ Calculating start block value: Sub-extent size = 64MB = (64 * 1024) KB = 65536 KB 
            Volume block size = 4KB
            Blocks in each sub-extent = (65536 / 4) = 16384
            Write 8 KB data starting at (16384 - 1) = 16383
            So, 8 KB data will span in two sub-extents;
            4KB in last block of first sub-extent and first block of second sub-extent
        """

        start_block = ((self.sub_extent_size / self.volume_block) - (self.volume_block / self.volume_block))
        fun_test.log("Start block for nvme write is {}".format(start_block))

        write = self.write_test(start_block)
        fun_test.test_assert_expected(True, write, "Write IO Completed")
        read = self.read_test(start_block)
        fun_test.test_assert_expected(True, read, "Read IO verification Completed")
        fun_test.log("Restarting F1....")
        self.f1_restart()
        fun_test.sleep("Waiting for the DPC server and DPCSH TCP proxy to settle down", self.iter_interval)
        fun_test.log("Read IO after F1 restart")
        read1 = self.read_test(start_block)
        fun_test.test_assert_expected(True, read1, "Read IO verification after F1 restart Completed")

    def cleanup(self):
        super(BLTF1RestartQemu, self).cleanup()


if __name__ == "__main__":
    blt_f1_restart_qemu = BLTF1RestartQemuScript()
    blt_f1_restart_qemu.add_test_case(BLTF1RestartQemu())
    blt_f1_restart_qemu.run()

