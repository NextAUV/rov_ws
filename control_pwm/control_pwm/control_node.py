import rclpy
from rclpy.node import Node
from joystick_msgs.msg import JoystickData
import serial
import numpy as np
import time
from rclpy.qos import QoSProfile, QoSReliabilityPolicy, QoSHistoryPolicy

qos = QoSProfile(
    reliability=QoSReliabilityPolicy.BEST_EFFORT,
    history=QoSHistoryPolicy.KEEP_LAST,
    depth=1
)


class ROVPWMController(Node):
    """
    This node subscribes to joystick data, calculates thruster PWM values
    using a mixing matrix, and sends them to an Arduino over serial.
    It includes a proper initialization sequence and robust error handling.
    """
    def __init__(self):
        super().__init__('rov_pwm_controller')

        # --- Initialize attributes FIRST to prevent AttributeError on failed connection ---
        self.arduino = None
        self.last_packet_sent = ""
        self.control_timer = None

        # --- Parameters ---
        self.declare_parameter('arduino_port', '/dev/ttyACM0')
        port = self.get_parameter('arduino_port').get_parameter_value().string_value
        
        try:
            self.arduino = serial.Serial(port, baudrate=115200, timeout=0.1)
            self.get_logger().info(f"Successfully connected to Arduino on {port}")
        except serial.SerialException as e:
            self.get_logger().error(f"Failed to connect to Arduino on {port}: {e}")
            self.get_logger().error("Shutting down node. Check the port and permissions (e.g., 'sudo chmod a+rw /dev/ttyACM0')")
            # Return without setting up the rest of the node.
            # The 'finally' block in main() will still call disarm_motors.
            return

        # --- Thruster Mixing Matrix (6x6) for BlueROV2-style frame ---
        # Maps [surge, sway, heave, roll, pitch, yaw] to 6 thrusters
        self.mixing_matrix = np.array([
            [1,  0,  0,  0,  1,  1],  # T1 (Front-Left-Horizontal)
            [1,  0,  0,  0, -1, -1],  # T2 (Front-Right-Horizontal)
            [1,  0,  0,  0, -1,  1],  # T3 (Rear-Left-Horizontal)
            [1,  0,  0,  0,  1, -1],  # T4 (Rear-Right-Horizontal)
            [0,  1,  1, -1,  0,  0],  # T5 (Front-Vertical)
            [0,  1, -1,  1,  0,  0],  # T6 (Rear-Vertical)
        ])

        # --- State ---
        self.thrust_input = np.zeros(6)
        
        # --- Arming Sequence ---
        self.get_logger().info("Waiting for Arduino to initialize...")
        time.sleep(2) # Wait for 2 seconds
        self.get_logger().info("Sending initial neutral signal.")
        for _ in range(5):
            self.send_pwm_packet([1500] * 6)
            time.sleep(0.1)

        # --- Subscribers ---
        self.create_subscription(
            JoystickData,
            'joystick_data',
            self.joystick_data_callback,
            qos
        )

        # --- Main Control Loop Timer ---
        self.control_timer = self.create_timer(0.05, self.run_control_loop) # 20 Hz
        self.get_logger().info("ROV PWM Controller Initialized and Armed.")

    def joystick_data_callback(self, msg):
        """Processes incoming joystick data and maps it to thrust inputs."""
        self.thrust_input = np.array([
            msg.x, msg.y, msg.z,
            msg.yaw, msg.pitch, msg.roll
        ])

    def run_control_loop(self):
        """Calculates and sends PWM signals based on the latest thrust input."""
        thrust_output = self.mixing_matrix @ self.thrust_input
        
        max_thrust = np.max(np.abs(thrust_output))
        if max_thrust > 1.0:
            thrust_output /= max_thrust
            
        thrust_pwm = [int(1500 + 400 * t) for t in thrust_output]
        self.send_pwm_packet(thrust_pwm)
        
    def send_pwm_packet(self, pwm_values):
        """Encodes and sends a list of PWM values to the Arduino."""
        # This check prevents errors if the serial port was never opened.
        if not self.arduino or not self.arduino.is_open:
            return

        packet = ','.join(str(p) for p in pwm_values) + '\n'
        
        if packet != self.last_packet_sent:
            self.get_logger().info(f"Sending PWM: {packet.strip()}")
            self.last_packet_sent = packet
            
        try:
            self.arduino.write(packet.encode('utf-8'))
        except Exception as e:
            self.get_logger().error(f"Serial write failed: {e}")

    def disarm_motors(self):
        """Sends a neutral signal to all motors and closes the connection."""
        self.get_logger().info("Disarming motors...")
        # Check if arduino object exists and is open before trying to use it.
        if self.arduino and self.arduino.is_open:
            try:
                self.send_pwm_packet([1500] * 6)
                time.sleep(0.1) # Ensure the packet is sent
                self.arduino.close()
                self.get_logger().info("Serial port closed.")
            except Exception as e:
                self.get_logger().error(f"Error while closing serial port: {e}")


def main(args=None):
    rclpy.init(args=args)
    node = ROVPWMController()
    
    # Only spin if the node was initialized correctly (arduino connected)
    if node.arduino and node.arduino.is_open:
        try:
            rclpy.spin(node)
        except KeyboardInterrupt:
            node.get_logger().info("Keyboard interrupt received.")
        finally:
            node.get_logger().info("Shutting down from spin.")
            node.disarm_motors()
            node.destroy_node()
    
    # If initialization failed, rclpy.ok() might still be true, so we clean up.
    if rclpy.ok():
        rclpy.shutdown()

if __name__ == '__main__':
    main()

