import rclpy
from rclpy.node import Node
from joystick_msgs.msg import JoystickData
import serial
import numpy as np
import time
from rclpy.qos import QoSProfile, QoSReliabilityPolicy, QoSHistoryPolicy
from geometry_msgs.msg import Twist

class ROVPWMController(Node):
    """
    This node subscribes to joystick data, calculates thruster PWM values
    using a mixing matrix, and sends them to an Arduino over serial.
    It includes a proper initialization sequence and robust error handling.
    """
    def __init__(self):
        super().__init__('rov_pwm_controller')

        # --- Initialize attributes FIRST ---
        self.arduino = None
        self.last_packet_sent = ""
        self.control_timer = None
        self.last_connection_attempt = 0
        self.connection_retry_interval = 2.0 # Seconds between retries

        # --- Parameters ---
        self.declare_parameter('arduino_port', '/dev/ttyACM0')
        self.port = self.get_parameter('arduino_port').get_parameter_value().string_value
        
        # Initial connection attempt
        self.connect_arduino()

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
        
        # --- QoS Profile for Teleop ---
        # Best Effort: Don't retry lost packets (low latency)
        # Volatile: Don't save old messages for new subscribers
        # Keep Last / Depth 1: Only keep the very latest command
        qos_profile = QoSProfile(
            reliability=QoSReliabilityPolicy.BEST_EFFORT,
            history=QoSHistoryPolicy.KEEP_LAST,
            depth=1
        )

        # --- Subscribers ---
        self.create_subscription(
            Twist,
            'cmd_vel',
            self.twist_callback,
            qos_profile
        )

        # --- Main Control Loop Timer ---
        self.control_timer = self.create_timer(0.05, self.run_control_loop) # 20 Hz
        self.get_logger().info("ROV PWM Controller Initialized.")

    def connect_arduino(self):
        """Attempts to connect to the Arduino."""
        now = time.time()
        if now - self.last_connection_attempt < self.connection_retry_interval:
            return False

        self.last_connection_attempt = now
        try:
            if self.arduino and self.arduino.is_open:
                self.arduino.close()
            
            # Added write_timeout to prevent blocking indefinitely
            self.arduino = serial.Serial(self.port, baudrate=115200, timeout=0.1, write_timeout=0.1)
            self.get_logger().info(f"Successfully connected to Arduino on {self.port}")
            
            # Arming Sequence on connect
            self.get_logger().info("Waiting for Arduino to initialize...")
            time.sleep(2) 
            self.get_logger().info("Sending initial neutral signal.")
            for _ in range(5):
                self.send_pwm_packet([1500] * 6)
                time.sleep(0.1)
            return True
        except serial.SerialException as e:
            self.get_logger().warn(f"Failed to connect to Arduino on {self.port}: {e}. Retrying in {self.connection_retry_interval}s...")
            self.arduino = None
            return False

    def run_control_loop(self):
        """Calculates and sends PWM signals based on the latest thrust input."""
        # Check connection
        if not self.arduino or not self.arduino.is_open:
            self.connect_arduino()
            return

        thrust_output = self.mixing_matrix @ self.thrust_input
        
        max_thrust = np.max(np.abs(thrust_output))
        if max_thrust > 1.0:
            thrust_output /= max_thrust
            
        thrust_pwm = [int(1500 + 400 * t) for t in thrust_output]
        self.send_pwm_packet(thrust_pwm)
        
    def send_pwm_packet(self, pwm_values):
        """Encodes and sends a list of PWM values to the Arduino."""
        if not self.arduino or not self.arduino.is_open:
            return

        packet = ','.join(str(p) for p in pwm_values) + '\n'
        
        # Only log if changed, to reduce spam
        if packet != self.last_packet_sent:
            # self.get_logger().info(f"Sending PWM: {packet.strip()}")
            self.last_packet_sent = packet
        
        try:
            self.arduino.write(packet.encode('utf-8'))
        except serial.SerialTimeoutException:
             self.get_logger().warn("Serial write timed out. Arduino might be busy or disconnected.")
             # We might want to trigger a reconnect here if it persists, but for now just warn
        except Exception as e:
            self.get_logger().error(f"Serial write failed: {e}")
            self.get_logger().warn("Closing serial connection and attempting to reconnect...")
            try:
                self.arduino.close()
            except:
                pass
            self.arduino = None

    def disarm_motors(self):
        """Sends a neutral signal to all motors and closes the connection."""
        self.get_logger().info("Disarming motors...")
        if self.arduino and self.arduino.is_open:
            try:
                self.send_pwm_packet([1500] * 6)
                time.sleep(0.1)
                self.arduino.close()
                self.get_logger().info("Serial port closed.")
            except Exception as e:
                self.get_logger().error(f"Error while closing serial port: {e}")

    def twist_callback(self, msg):
        self.thrust_input = np.array([
            msg.linear.x,   # surge
            msg.linear.y,   # sway
            msg.linear.z,   # heave
            msg.angular.z,  # yaw
            msg.angular.y,  # pitch
            msg.angular.x   # roll
        ])

def main(args=None):
    rclpy.init(args=args)
    node = ROVPWMController()
    
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        node.get_logger().info("Keyboard interrupt received.")
    finally:
        node.get_logger().info("Shutting down from spin.")
        node.disarm_motors()
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()

if __name__ == '__main__':
    main()

