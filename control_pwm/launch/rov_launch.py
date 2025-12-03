from launch import LaunchDescription
from launch_ros.actions import Node

def generate_launch_description():
    return LaunchDescription([
        Node(
            package='control_pwm',
            executable='control_node',
            name='control_node',
            output='screen',
            parameters=[
                {'arduino_port': '/dev/ttyACM0'}
            ]
        ),
        Node(
            package='control_pwm',
            executable='web_node',
            name='web_node',
            output='screen'
        )
    ])
