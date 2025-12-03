import rclpy
from rclpy.node import Node
import http.server
import socketserver
import os
import threading
import time
from ament_index_python.packages import get_package_share_directory
from geometry_msgs.msg import Twist
from rclpy.qos import QoSProfile, QoSReliabilityPolicy, QoSHistoryPolicy

# Custom handler to process POST requests and publish to ROS 2
class RosRequestHandler(http.server.SimpleHTTPRequestHandler):
    # These will be class-level variables to hold references to the node's components
    node_logger = None
    ros_publisher = None

    def do_GET(self):
        if self.path == '/health':
            self.send_response(200)
            self.send_header('Content-type', 'text/plain')
            self.end_headers()
            self.wfile.write(b"OK")
        else:
            # Serve static files for other GET requests
            super().do_GET()

    def do_POST(self):
        if self.path == '/data':
            try:
                content_length = int(self.headers['Content-Length'])
                post_data = self.rfile.read(content_length)
                data_string = post_data.decode('utf-8')
                
                # Parsing Data Safely
                parts = data_string.split(',')
                if len(parts) != 6:
                    if self.node_logger:
                        self.node_logger.warn(f"Received malformed data: expected 6 values, got {len(parts)}")
                    self.send_error(400, "Bad Request: Malformed data")
                    return
                
                # Convert all parts to float, safely
                values = [float(p) for p in parts]

                # Creating and Publishing a ROS 2 Message
                if self.ros_publisher:
                    twist_msg = Twist()
                    # Map the UI values to the Twist message fields
                    # [x, y, z, yaw, pitch, roll] from JS
                    twist_msg.linear.x = values[0]  # Forward/Backward
                    twist_msg.linear.y = values[1]  # Up/Down
                    twist_msg.linear.z = values[2]  # Strafe Left/Right
                    twist_msg.angular.z = values[3] # Turn Left/Right (Yaw)
                    twist_msg.angular.y = values[4] # Pitch
                    twist_msg.angular.x = values[5] # Roll
                    
                    self.ros_publisher.publish(twist_msg)
                    # Logging every message can be spammy, maybe log only occasionally or debug
                    # self.node_logger.debug(f"Published: {values}")

                self.send_response(200)
                self.end_headers()

            except (ValueError, IndexError) as e:
                if self.node_logger:
                    self.node_logger.error(f"Could not parse controller data: {e}")
                self.send_error(400, "Bad Request: Invalid data format")
            except Exception as e:
                if self.node_logger:
                    self.node_logger.error(f"An unexpected error occurred: {e}")
                self.send_error(500, "Internal Server Error")
        else:
            self.send_error(404, "File Not Found")

    def log_message(self, format, *args):
        # Override to prevent printing every request to stdout, use ROS logger if needed
        pass

# Custom Server class to allow address reuse and threading
class RosTCPServer(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True

class WebServerNode(Node):
    def __init__(self):
        super().__init__('web_server_node')
        
        # --- QoS Profile for Teleop ---
        qos_profile = QoSProfile(
            reliability=QoSReliabilityPolicy.BEST_EFFORT,
            history=QoSHistoryPolicy.KEEP_LAST,
            depth=1
        )

        # --- Create the ROS 2 Publisher ---
        self.publisher_ = self.create_publisher(Twist, 'cmd_vel', qos_profile)
        self.get_logger().info('ROS 2 Web Server started. Publishing to /cmd_vel with Best Effort QoS.')

        # Find the 'web' directory
        try:
            pkg_share_dir = get_package_share_directory('control_pwm')
            web_dir = os.path.join(pkg_share_dir, 'web')
            if os.path.exists(web_dir):
                os.chdir(web_dir)
                self.get_logger().info(f"Serving files from: {web_dir}")
            else:
                self.get_logger().error(f"Web directory not found at: {web_dir}")
        except Exception as e:
             self.get_logger().error(f"Could not setup web directory: {e}")
        
        # --- Pass the node's publisher and logger to the handler ---
        RosRequestHandler.node_logger = self.get_logger()
        RosRequestHandler.ros_publisher = self.publisher_
        
        # --- Running the Server in a Separate Thread ---
        self.port = 8000
        self.httpd = None
        self.server_thread = None
        self.start_server()

    def start_server(self):
        try:
            self.httpd = RosTCPServer(("", self.port), RosRequestHandler)
            self.server_thread = threading.Thread(target=self.httpd.serve_forever)
            self.server_thread.daemon = True
            self.server_thread.start()
            self.get_logger().info(f"HTTP server is running in the background on port {self.port}")
        except OSError as e:
            self.get_logger().error(f"Failed to start server on port {self.port}: {e}")
            # Retry logic could go here, but for now we just log it.

    def destroy_node(self):
        self.get_logger().info("Shutting down the HTTP server...")
        if self.httpd:
            self.httpd.shutdown()
            self.httpd.server_close()
        self.get_logger().info("HTTP server shut down.")
        super().destroy_node()

def main(args=None):
    rclpy.init(args=args)
    web_server_node = WebServerNode()
    try:
        rclpy.spin(web_server_node)
    except KeyboardInterrupt:
        pass
    finally:
        web_server_node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()

if __name__ == '__main__':
    main()