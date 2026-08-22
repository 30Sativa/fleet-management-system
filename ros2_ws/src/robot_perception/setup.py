from glob import glob
import os

from setuptools import find_packages, setup


package_name = 'robot_perception'

setup(
    name=package_name,
    version='0.1.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages',
         [os.path.join('resource', package_name)]),
        (os.path.join('share', package_name), ['package.xml']),
        (os.path.join('share', package_name, 'launch'),
         glob(os.path.join('launch', '*.launch.py'))),
        (os.path.join('share', package_name, 'config'),
         glob(os.path.join('config', '*.yaml'))),
        (os.path.join('share', package_name, 'scripts'),
         glob(os.path.join('scripts', '*.py'))),
    ],
    install_requires=['setuptools'],
    entry_points={
        'console_scripts': [
            'person_perception = robot_perception.person_perception_node:main',
        ],
    },
    zip_safe=True,
    maintainer='Duy',
    maintainer_email='caoduy856@gmail.com',
    description='Phase 4: RGB-D person perception feeding Nav2 speed limits.',
    license='Apache-2.0',
    tests_require=['pytest'],
)
