#!/usr/bin/env python3
import rclpy
from rclpy.node import Node
from joystick_msgs.msg import JoystickData
import sys
import select
import termios
import tty
import threading
import numpy as np # Import numpy for clamping

# A dictionary to map keys to their corresponding axes and directions
KEY_MAP = {
    'w': ('pitch', 1.0), 's': ('pitch', -1.0),
    'd': ('yaw', 1.0), 'a': ('yaw', -1.0),
    'i': ('x', 1.0), 'k': ('x', -1.0),
    'l': ('z', 1.0), 'j': ('z', -1.0),
    'u': ('y', 1.0), 'o': ('y', -1.0),
}

# Key for stopping all motion
STOP_KEY = ' ' # Spacebar

class TeleopKeyboardPublisher(Node):
    """
    A ROS2 node that captures keyboard strokes and publishes them as JoystickData messages.
    """
    def __init__(self):
        super().__init__('teleop_keyboard_publisher')
        
        # Create a publisher for the 'joystick_data' topic
        self.publisher_ = self.create_publisher(JoystickData, 'joystick_data', 10)
        
        # --- Parameters ---
        self.declare_parameter('move_increment', 0.2) # 20% increment
        self.move_increment = self.get_parameter('move_increment').get_parameter_value().double_value
        
        # Store the current state of the joystick message
        self.msg = JoystickData()
        self.msg.x = 0.0
        self.msg.y = 0.0
        self.msg.z = 0.0
        self.msg.pitch = 0.0
        self.msg.yaw = 0.0
        self.msg.roll = 0.0 # Roll is not used in this teleop
        
        # For reading keyboard input
        self.settings = termios.tcgetattr(sys.stdin)
        
        self.print_instructions()

    def print_instructions(self):
        """Prints the keybindings and instructions to the console."""
        self.get_logger().info("Teleop Keyboard Publisher is running...")
        self.get_logger().info("-------------------------------------------")
        self.get_logger().info("           w/s: Increase/Decrease Pitch")
        self.get_logger().info("           a/d: Increase/Decrease Yaw")
        self.get_logger().info("           i/k: Increase/Decrease Forward/Backward (x)")
        self.get_logger().info("           j/l: Increase/Decrease Strafe (z)")
        self.get_logger().info("           u/o: Increase/Decrease Up/Down (y)")
        self.get_logger().info("-------------------------------------------")
        self.get_logger().info("       <spacebar>: Hard Stop (Reset all to 0)")
        self.get_logger().info("         (Ctrl+C to quit)")
        self.get_logger().info("-------------------------------------------")


    def get_key(self):
        """Waits for a keypress and returns the character."""
        tty.setraw(sys.stdin.fileno())
        select.select([sys.stdin], [], [], 0)
        key = sys.stdin.read(1)
        termios.tcsetattr(sys.stdin, termios.TCSADRAIN, self.settings)
        return key

    def run_teleop(self):
        """The main loop that reads keys and publishes messages."""
        while rclpy.ok():
            key = self.get_key()

            if key:
                if key in KEY_MAP:
                    axis, direction = KEY_MAP[key]
                    
                    # Get the current value of the axis
                    current_value = getattr(self.msg, axis)
                    
                    # Calculate the new value by adding/subtracting the increment
                    new_value = current_value + (direction * self.move_increment)
                    
                    # Clamp the value to be between -1.0 and 1.0
                    new_value = np.clip(new_value, -1.0, 1.0)
                    
                    # Set the new clamped value
                    setattr(self.msg, axis, new_value)

                elif key == STOP_KEY:
                    # If spacebar is pressed, reset all values to zero
                    self.msg.x = 0.0
                    self.msg.y = 0.0
                    self.msg.z = 0.0
                    self.msg.pitch = 0.0
                    self.msg.yaw = 0.0
                    self.msg.roll = 0.0
                    self.get_logger().warn("--- EMERGENCY STOP ---")

                elif key == '\x03': # Ctrl+C
                    break
                
                # Log the current values to the screen after a key press
                self.get_logger().info(
                    f"Speeds: x={self.msg.x:.2f}, y={self.msg.y:.2f}, z={self.msg.z:.2f}, "
                    f"pitch={self.msg.pitch:.2f}, yaw={self.msg.yaw:.2f}"
                )
            
            # Continuously publish the message
            self.publisher_.publish(self.msg)

def main(args=None):
    rclpy.init(args=args)
    node = TeleopKeyboardPublisher()
    
    # Run the teleop logic in a separate thread
    teleop_thread = threading.Thread(target=node.run_teleop)
    teleop_thread.start()
    
    # Spin the node to keep it alive
    rclpy.spin(node)

    # Cleanup
    teleop_thread.join()
    node.destroy_node()
    rclpy.shutdown()

if __name__ == '__main__':
    main()
#!/usr/bin/env python3
# import rclpy
# from rclpy.node import Node
# from joystick_msgs.msg import JoystickData  # Import your custom message
# import sys
# import select
# import termios
# import tty
# import threading

# # A dictionary to map keys to their corresponding axes and directions
# KEY_MAP = {
#     'w': ('pitch', 1.0), 's': ('pitch', -1.0),
#     'd': ('yaw', 1.0), 'a': ('yaw', -1.0),
#     'i': ('x', 1.0), 'k': ('x', -1.0),
#     'l': ('z', 1.0), 'j': ('z', -1.0),
#     'u': ('y', 1.0), 'o': ('y', -1.0),
# }

# # Key for stopping all motion
# STOP_KEY = ' ' # Spacebar

# class TeleopKeyboardPublisher(Node):
#     """
#     A ROS2 node that captures keyboard strokes and publishes them as JoystickData messages.
#     """
#     def __init__(self):
#         super().__init__('teleop_keyboard_publisher')
        
#         # Create a publisher for the 'joystick_data' topic
#         self.publisher_ = self.create_publisher(JoystickData, 'joystick_data', 10)
        
#         # --- Parameters ---
#         self.declare_parameter('move_increment', 0.2) # 20% increment
#         self.move_increment = self.get_parameter('move_increment').get_parameter_value().double_value
        
#         # Store the current state of the joystick message
#         self.msg = JoystickData()
#         self.msg.x = 0.0
#         self.msg.y = 0.0
#         self.msg.z = 0.0
#         self.msg.pitch = 0.0
#         self.msg.yaw = 0.0
#         self.msg.roll = 0.0 # Roll is not used in this teleop
        
#         # For reading keyboard input
#         self.settings = termios.tcgetattr(sys.stdin)
        
#         self.print_instructions()

#     def print_instructions(self):
#         """Prints the keybindings and instructions to the console."""
#         self.get_logger().info("Teleop Keyboard Publisher is running...")
#         self.get_logger().info("-------------------------------------------")
#         self.get_logger().info("           w: pitch forward")
#         self.get_logger().info(" a: yaw left | s: pitch back | d: yaw right")
#         self.get_logger().info("-------------------------------------------")
#         self.get_logger().info("           i: move forward (x+)")
#         self.get_logger().info(" j: strafe left (z+) | k: move back (x-) | l: strafe right (z-)")
#         self.get_logger().info("-------------------------------------------")
#         self.get_logger().info("           u: move up (y+)")
#         self.get_logger().info("           o: move down (y-)")
#         self.get_logger().info("-------------------------------------------")
#         self.get_logger().info("       <spacebar>: Stop all movement")
#         self.get_logger().info("         (Ctrl+C to quit)")
#         self.get_logger().info("-------------------------------------------")


#     def get_key(self):
#         """Waits for a keypress and returns the character."""
#         tty.setraw(sys.stdin.fileno())
#         select.select([sys.stdin], [], [], 0)
#         key = sys.stdin.read(1)
#         termios.tcsetattr(sys.stdin, termios.TCSADRAIN, self.settings)
#         return key

#     def run_teleop(self):
#         """The main loop that reads keys and publishes messages."""
#         while rclpy.ok():
#             key = self.get_key()
            
#             # Reset all axes to zero for each new key press
#             # This makes the robot stop if a key is not being pressed
#             self.msg.x = 0.0
#             self.msg.y = 0.0
#             self.msg.z = 0.0
#             self.msg.pitch = 0.0
#             self.msg.yaw = 0.0

#             if key:
#                 # If the pressed key is in our map, update the message
#                 if key in KEY_MAP:
#                     axis, direction = KEY_MAP[key]
#                     setattr(self.msg, axis, direction * self.move_increment)
#                 # If the stop key is pressed, all values are already zero
#                 elif key == STOP_KEY:
#                     pass
#                 # If Ctrl+C is pressed, the key will be '\x03'
#                 elif key == '\x03':
#                     break
            
#             # Publish the message, whether a key was pressed or not
#             self.publisher_.publish(self.msg)

# def main(args=None):
#     rclpy.init(args=args)
#     node = TeleopKeyboardPublisher()
    
#     # Run the teleop logic in a separate thread
#     teleop_thread = threading.Thread(target=node.run_teleop)
#     teleop_thread.start()
    
#     # Spin the node to keep it alive
#     rclpy.spin(node)

#     # Cleanup
#     teleop_thread.join()
#     node.destroy_node()
#     rclpy.shutdown()

# if __name__ == '__main__':
#     main()