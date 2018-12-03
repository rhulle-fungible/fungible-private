from lib.system.fun_test import *
from lib.host.linux import Linux

class LinuxServer():

    def ssh_and_ping(self):
        result = False
        linux_obj = Linux(host_ip="qa-ubuntu-02", ssh_username="auto_admin", ssh_password="fun123")


        ping_res = linux_obj.ping("127.0.0.1",count=2,max_percentage_loss="0")
        if ping_res == True:
            fun_test.log("Success")
        else:
            fun_test.log("Fail")

        # ping_res = linux_obj.command(command="ping 127.0.0.1 -c 4")
        # fun_test.test_assert(expression=ping_res == True, message="Linux server is pingable")


if __name__ == "__main__":
    linux_ping = LinuxServer()
    ping_result = linux_ping.ssh_and_ping()

#fun_test.log(ping_server)
#    fun_test.log("Linux server is alive")
