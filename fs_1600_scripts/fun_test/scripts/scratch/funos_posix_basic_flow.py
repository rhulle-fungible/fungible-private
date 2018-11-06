from lib.system.fun_test import *
from lib.topology.topology_helper import TopologyHelper
from lib.host.storage_controller import StorageController
from lib.system import utils

import os
os.environ["DOCKER_HOSTS_SPEC_FILE"] = fun_test.get_script_parent_directory() + "/remote_docker_host_with_storage.json"


class MyScript(FunTestScript):
    def describe(self):
        self.set_test_details(steps="""
        1. Setup one F1 container
        2. Setup traffic generator container - fio
        """)

    def setup(self):
        spec_file = fun_test.get_script_parent_directory() + "/single_f1_dpcsh_and_tg_fio.json"
        # topology_obj_helper = TopologyHelper(spec_file="./single_f1_dpcsh_and_tg_fio.json")
        topology_obj_helper = TopologyHelper(spec_file=spec_file)
        topology = topology_obj_helper.deploy()
        fun_test.test_assert(topology, "Ensure deploy is successful")
        fun_test.shared_variables["topology"] = topology

    def cleanup(self):
        TopologyHelper(spec=fun_test.shared_variables["topology"]).cleanup()
        # pass


class FunTestCase1(FunTestCase):
    def describe(self):
        self.set_test_details(id=1,
                              summary="Configure volume and Run traffic using fio",
                              steps="""
        1. Use StorageController to connect to the dpcsh tcp proxy to F1
        2. Configure ip_cfg
        3. Create volume
        4. Attach volume to remote server
        5. Run fio from remote server
                              """)

    def setup(self):
        pass

    def cleanup(self):
        pass

    def run(self):
        topology = fun_test.shared_variables["topology"]
        dut_instance0 = topology.get_dut_instance(index=0)
        fun_test.test_assert(dut_instance0, "Retrieved dut instance 0")

        linux_host = topology.get_tg_instance(tg_index=0)

        config_file = fun_test.get_script_parent_directory() + "/funos_posix_basic_flow_config.json"
        fun_test.log("Config file being used: {}".format(config_file))
        config_dict = {}
        config_dict = utils.parse_file_to_json(config_file)

        # parameters required for dpcsh command execution
        thin_uuid = utils.generate_uuid()

        volume_capacity = config_dict["FunTestCase1"]["volume_params"]["capacity"]
        block_size = config_dict["FunTestCase1"]["volume_params"]["block_size"]
        volume_name = config_dict["FunTestCase1"]["volume_params"]["name"]
        ns_id = config_dict["FunTestCase1"]["volume_params"]["ns_id"]
        volume_type = config_dict["FunTestCase1"]["volume_params"]["type"]

        storage_controller = StorageController(target_ip=dut_instance0.host_ip,
                                               target_port=dut_instance0.external_dpcsh_port)

        # Configuring controller
        result_ip_cfg = storage_controller.ip_cfg(ip=dut_instance0.data_plane_ip)
        fun_test.test_assert(result_ip_cfg["status"], "ip_cfg {} on Dut Instance".format(dut_instance0.data_plane_ip))

        # Creating Thin block volume
        result_create_volume = storage_controller.create_thin_block_volume(capacity=volume_capacity,
                                                                           block_size=block_size, uuid=thin_uuid,
                                                                           name=volume_name)
        fun_test.test_assert(result_create_volume["status"], "Thin Block volume is created")

        # Attaching volume to remote server - to linux container
        result_attach_volume = storage_controller.volume_attach_remote(uuid=thin_uuid, ns_id= ns_id,
                                                                       remote_ip=linux_host.internal_ip)
        fun_test.test_assert(result_attach_volume["status"], "Thin Block volume is attached")

        storage_props_tree = "{}/{}/{}/{}".format("storage", "volumes", volume_type, thin_uuid)

        initial_volume_status = {}
        command_result = storage_controller.peek(storage_props_tree)
        fun_test.simple_assert(command_result["status"], "Initial volume stats of DUT Instance 0")
        initial_volume_status = command_result["data"]
        fun_test.log("Volume Status at the beginning of the test:")
        fun_test.log(initial_volume_status)
        volume_status_read = command_result["data"]["num_reads"]
        volume_status_write = command_result["data"]["num_writes"]
        initial_counter_stat = 0

        fun_test.test_assert_expected(expected=initial_counter_stat, actual=volume_status_write,
                                      message="Write counter is correct")
        fun_test.test_assert_expected(expected=initial_counter_stat, actual=volume_status_read,
                                      message="Read counter is correct")

        # Generating traffic from remote server using fio
        destination_ip = dut_instance0.data_plane_ip

        # Parameters required for fio execution
        # rw_mode = config_dict["FunTestCase1"]["fio_params"]["rw_mode"]
        write_mode = config_dict["FunTestCase1"]["fio_params"]["write_mode"]
        read_mode = config_dict["FunTestCase1"]["fio_params"]["read_mode"]
        fio_block_size = config_dict["FunTestCase1"]["fio_params"]["fio_block_size"]
        fio_iodepth = config_dict["FunTestCase1"]["fio_params"]["fio_iodepth"]
        size = config_dict["FunTestCase1"]["fio_params"]["size"]

        fio_result = linux_host.remote_fio(destination_ip=destination_ip, rw=write_mode,
                                           bs=fio_block_size, iodepth=fio_iodepth, size=size)
        fio_result = linux_host.remote_fio(destination_ip=destination_ip, rw=read_mode,
                                           bs=fio_block_size, iodepth=fio_iodepth, size=size)

        volume_status = {}
        command_result = storage_controller.peek(storage_props_tree)
        fun_test.simple_assert(command_result["status"], "Volume stats of DUT Instance 0 after IO")
        volume_status = command_result["data"]
        fun_test.log(volume_status)
        volume_status_write = command_result["data"]["num_writes"]
        volume_status_read = command_result["data"]["num_reads"]
        expected_counter_stat = int(filter(str.isdigit, str(size)))/int(filter(str.isdigit, str(fio_block_size)))
        fun_test.log(expected_counter_stat)

        fun_test.test_assert_expected(expected=expected_counter_stat, actual=volume_status_write,
                                      message="Write counter is correct")
        fun_test.test_assert_expected(expected=expected_counter_stat, actual=volume_status_read,
                                      message="Read counter is correct")

        result_detach_volume = storage_controller.volume_detach_remote(ns_id=ns_id, uuid=thin_uuid,
                                                                       remote_ip=linux_host.internal_ip)
        fun_test.test_assert(result_detach_volume["status"], "Thin Block volume is detached")
        result_delete_volume = storage_controller.delete_thin_block_volume(capacity=volume_capacity, uuid=thin_uuid,
                                                                           block_size=block_size, name=volume_name)
        fun_test.test_assert(result_delete_volume["status"], "Thin Block volume is deleted")


if __name__ == "__main__":
    myscript = MyScript()
    myscript.add_test_case(FunTestCase1())
    myscript.run()
