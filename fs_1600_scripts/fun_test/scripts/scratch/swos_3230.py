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
        """)

    def setup(self):
        topology_obj_helper = TopologyHelper(spec_file="./swos_3230_single_f1_custom_app.json")
        topology = topology_obj_helper.deploy()
        fun_test.test_assert(topology, "Ensure deploy is successful")
        fun_test.shared_variables["topology"] = topology

    def cleanup(self):
        # TopologyHelper(spec=fun_test.shared_variables["topology"]).cleanup()
        pass


class FunTestCase1(FunTestCase):
    def describe(self):
        self.set_test_details(id=1,
                              summary="SWOS-3230: Volume Detach Failure Fix Verification",
                              steps="""
        1. Use StorageController to connect to the dpcsh tcp proxy to F1
        2. Configure ip_cfg
        3. Create volume
        4. Attach volume to remote server
        5. Detach volume from remote server
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

        config_file = fun_test.get_script_parent_directory() + "/swos_3230_config.json"
        fun_test.log("Config file being used: {}".format(config_file))
        config_dict = utils.parse_file_to_json(config_file)

        # Config parameters required for volume operations
        thin_uuid = utils.generate_uuid()
        volume_capacity = config_dict["FunTestCase1"]["volume_params"]["capacity"]
        block_size = config_dict["FunTestCase1"]["volume_params"]["block_size"]
        volume_name = config_dict["FunTestCase1"]["volume_params"]["name"]
        ns_id = config_dict["FunTestCase1"]["volume_params"]["ns_id"]

        storage_controller = StorageController(target_ip=dut_instance0.host_ip,
                                               target_port=dut_instance0.external_dpcsh_port)

        result_ip_cfg = storage_controller.ip_cfg(ip=dut_instance0.data_plane_ip)
        fun_test.test_assert(result_ip_cfg["status"], "ip_cfg {} on Dut Instance".format(dut_instance0.data_plane_ip))

        # Creating Thin volume
        result_create_volume = storage_controller.create_thin_block_volume(capacity=volume_capacity,
                                                                           block_size=block_size, uuid=thin_uuid,
                                                                           name=volume_name)
        fun_test.test_assert(result_create_volume["status"], "Thin Block volume is created")

        # Attaching volume to remote server
        result_attach_volume = storage_controller.volume_attach_remote(ns_id=ns_id, uuid=thin_uuid,
                                                                       remote_ip=linux_host.internal_ip)
        fun_test.test_assert(result_attach_volume["status"], "Thin Block volume is attached")

        # Detaching volume - this should not fail or cause funos to crash
        result_detach_volume = storage_controller.volume_detach_remote(ns_id=ns_id, uuid=thin_uuid,
                                                                       remote_ip=dut_instance0.data_plane_ip)
        fun_test.test_assert(result_detach_volume["status"], "Thin Block volume is detached")


if __name__ == "__main__":
    myscript = MyScript()
    myscript.add_test_case(FunTestCase1())
    myscript.run()
