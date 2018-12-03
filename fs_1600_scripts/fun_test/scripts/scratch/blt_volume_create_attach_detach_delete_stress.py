from lib.system.fun_test import *
from lib.topology.topology_helper import TopologyHelper
from lib.host.storage_controller import StorageController
from lib.system import utils

import os
os.environ["DOCKER_HOSTS_SPEC_FILE"] = fun_test.get_script_parent_directory() + "/remote_docker_host_with_storage.json"


class BltCreateAttachDetachDeleteVol(FunTestScript):
    def describe(self):
        self.set_test_details(steps="""
        1. Setup one F1 container
        2. Setup traffic generator container - fio
        """)

    def setup(self):
        spec_file = fun_test.get_script_parent_directory() + "/thin_block_volume_sanity_tb.json"
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
        4. Attach volume
        5. Detach volume
        6. Delete volume
        7. Repeat step 4 and 5 repeatedly
        8. Verify no error or funos crash occurs
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

        config_file = fun_test.get_script_parent_directory() + "/thin_block_volume_sanity_config.json"
        fun_test.log("Config file being used: {}".format(config_file))
        config_dict = {}
        config_dict = utils.parse_file_to_json(config_file)

        # parameters required for dpcsh command execution
        volume_capacity = config_dict["FunTestCase1"]["volume_params"]["capacity"]
        block_size = config_dict["FunTestCase1"]["volume_params"]["block_size"]
        volume_name = config_dict["FunTestCase1"]["volume_params"]["name"]
        ns_id = config_dict["FunTestCase1"]["volume_params"]["ns_id"]
        # volume_type = config_dict["FunTestCase1"]["volume_params"]["type"]

        storage_controller = StorageController(target_ip=dut_instance0.host_ip,
                                               target_port=dut_instance0.external_dpcsh_port)

        # Configuring controller
        result_ip_cfg = storage_controller.ip_cfg(ip=dut_instance0.data_plane_ip)
        fun_test.test_assert(result_ip_cfg["status"], "ip_cfg {} on Dut Instance".format(dut_instance0.data_plane_ip))

        # TODO: To add more stress, should we do multi-threading? iterator value
        for iterator in xrange(0, 1001, 1):
            thin_uuid = utils.generate_uuid()

            # Creating Thin block volume
            fun_test.log("============ Iteration #{} ============".format(iterator))
            result_create_volume = storage_controller.create_thin_block_volume(capacity=volume_capacity,
                                                                               block_size=block_size, uuid=thin_uuid,
                                                                               name=volume_name)
            fun_test.test_assert(result_create_volume["status"],
                                 "Iter {} - Thin Block volume is created".format(iterator))

            # Attach volume
            result_attach_volume = storage_controller.volume_attach_remote(uuid=thin_uuid, ns_id=ns_id,
                                                                           remote_ip=linux_host.internal_ip)
            fun_test.test_assert(result_attach_volume["status"], "Thin Block volume is attached")

            # Detach volume
            result_detach_volume = storage_controller.volume_detach_remote(ns_id=ns_id, uuid=thin_uuid,
                                                                           remote_ip=linux_host.internal_ip)
            fun_test.test_assert(result_detach_volume["status"], "Thin Block volume is detached")

            # Deleting Thin block volume
            result_delete_volume = storage_controller.delete_thin_block_volume(capacity=volume_capacity, uuid=thin_uuid,
                                                                               block_size=block_size, name=volume_name)
            fun_test.test_assert(result_delete_volume["status"],
                                 "Iter {} - Thin Block volume is deleted".format(iterator))

        '''
        storage_props_tree = "{}/{}/{}/{}/{}".format("storage", "volumes", volume_type, thin_uuid, "stats")
        command_result = storage_controller.peek(storage_props_tree)
        fun_test.log(command_result)
        fun_test.test_assert_expected(expected=False, actual=command_result["status"],
                                      message="Stat and Counters are reset after deleting volume")
        '''


if __name__ == "__main__":
    blt_create_attach_detach_del_vol = BltCreateAttachDetachDeleteVol()
    blt_create_attach_detach_del_vol.add_test_case(FunTestCase1())
    blt_create_attach_detach_del_vol.run()
