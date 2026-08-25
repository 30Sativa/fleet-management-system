from glob import glob
import os

from setuptools import find_packages, setup


package_name = 'stm32_bridge'

setup(
    name=package_name,
    version='0.1.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages',
         [os.path.join('resource', package_name)]),
        (os.path.join('share', package_name), ['package.xml', 'README.md']),
        (os.path.join('share', package_name, 'launch'),
         glob(os.path.join('launch', '*.launch.py'))),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='Duy',
    maintainer_email='caoduy856@gmail.com',
    description='ROS2 serial bridge from /cmd_vel to the STM32 motor controller.',
    license='Apache-2.0',
    tests_require=['pytest'],
    entry_points={
        'console_scripts': [
            'stm32_bridge_node = stm32_bridge.stm32_bridge_node:main',
        ],
    },
)
