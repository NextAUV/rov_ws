import rclpy
from rclpy.node import Node
import http.server
import socketserver
import os
import threading # We need threading to run the server and ROS 2 node together
from ament_index_python.packages import get_package_share_directory
from geometry_msgs.msg import Twist # The standard message for velocity commands
from rclpy.qos import QoSProfile, QoSReliabilityPolicy, QoSHistoryPolicy

# qos = QoSProfile(
#     reliability=QoSReliabilityPolicy.BEST_EFFORT,
#     history=QoSHistoryPolicy.KEEP_LAST,
#     depth=1
# )

# Custom handler to process POST requests and publish to ROS 2
class RosRequestHandler(http.server.SimpleHTTPRequestHandler):
    # These will be class-level variables to hold references to the node's components
    node_logger = None
    ros_publisher = None

    def do_POST(self):
        if self.path == '/data':
            try:
                content_length = int(self.headers['Content-Length'])
                post_data = self.rfile.read(content_length)
                data_string = post_data.decode('utf-8')
                
                # --- Problem 1: Parsing Data Safely ---
                # Split the string by commas and convert to numbers
                parts = data_string.split(',')
                if len(parts) != 6:
                    self.node_logger.warn(f"Received malformed data: expected 6 values, got {len(parts)}")
                    self.send_error(400, "Bad Request: Malformed data")
                    return
                
                # Convert all parts to float, safely
                values = [float(p) for p in parts]

                # --- Problem 2: Creating and Publishing a ROS 2 Message ---
                if self.ros_publisher:
                    # Create a Twist message
                    twist_msg = Twist()
                    # Map the UI values to the Twist message fields
                    # [x, y, z, yaw, pitch, roll] from JS
                    twist_msg.linear.x = values[0]  # Forward/Backward
                    twist_msg.linear.y = values[1]  # Up/Down
                    twist_msg.linear.z = values[2]  # Strafe Left/Right
                    twist_msg.angular.z = values[3] # Turn Left/Right (Yaw)
                    twist_msg.angular.y = values[4] # Pitch
                    twist_msg.angular.x = values[5] # Roll
                    
                    # Publish the message!
                    self.ros_publisher.publish(twist_msg)
                    self.node_logger.info(f"Published to /cmd_vel: linear=[{values[0]:.2f}, {values[1]:.2f}, {values[2]:.2f}], angular=[{values[5]:.2f}, {values[4]:.2f}, {values[3]:.2f}]")

                self.send_response(200)
                self.end_headers()

            except (ValueError, IndexError) as e:
                self.node_logger.error(f"Could not parse controller data: {e}")
                self.send_error(400, "Bad Request: Invalid data format")
            except Exception as e:
                self.node_logger.error(f"An unexpected error occurred: {e}")
                self.send_error(500, "Internal Server Error")
        else:
            self.send_error(404, "File Not Found")

class WebServerNode(Node):
    def __init__(self):
        super().__init__('web_server_node')
        
        # --- Create the ROS 2 Publisher ---
        self.publisher_ = self.create_publisher(Twist, 'cmd_vel',10)
        self.get_logger().info('ROS 2 Web Server started. Publishing to /cmd_vel.')

        # Find the 'web' directory
        pkg_share_dir = get_package_share_directory('control_pwm')
        web_dir = os.path.join(pkg_share_dir, 'web')
        os.chdir(web_dir)
        
        # --- Pass the node's publisher and logger to the handler ---
        RosRequestHandler.node_logger = self.get_logger()
        RosRequestHandler.ros_publisher = self.publisher_
        
        # --- Problem 3: Running the Server in a Separate Thread ---
        PORT = 8000
        # The httpd object will be created but not started in a blocking way
        self.httpd = socketserver.TCPServer(("", PORT), RosRequestHandler)
        
        # Start serve_forever() in a background thread
        self.server_thread = threading.Thread(target=self.httpd.serve_forever)
        self.server_thread.daemon = True
        self.server_thread.start()

        self.get_logger().info(f"HTTP server is running in the background on port {PORT}")

    def destroy_node(self):
        self.get_logger().info("Shutting down the HTTP server.")
        self.httpd.shutdown() # Properly stop the server
        self.httpd.server_close()
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
        rclpy.shutdown()

if __name__ == '__main__':
    main()