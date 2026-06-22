ARG ROS_DISTRO=humble
FROM ros:${ROS_DISTRO}-ros-base

ARG ROS_DISTRO
ENV ROS_DISTRO=${ROS_DISTRO}
ENV ROS_WS=/ros2_ws

SHELL ["/bin/bash", "-c"]

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    cmake \
    git \
    python3-colcon-common-extensions \
    python3-rosdep \
    && rm -rf /var/lib/apt/lists/*

RUN if [ ! -f /etc/ros/rosdep/sources.list.d/20-default.list ]; then \
      rosdep init; \
    fi && \
    rosdep update --rosdistro "${ROS_DISTRO}"

WORKDIR ${ROS_WS}
COPY ros2_ws/src ./src

RUN apt-get update && \
    rosdep install \
      --from-paths src \
      --ignore-src \
      --rosdistro "${ROS_DISTRO}" \
      -r -y && \
    rm -rf /var/lib/apt/lists/*

RUN source "/opt/ros/${ROS_DISTRO}/setup.bash" && \
    colcon build

COPY docker/ros_entrypoint.sh /ros_entrypoint.sh
RUN chmod +x /ros_entrypoint.sh

ENTRYPOINT ["/ros_entrypoint.sh"]
CMD ["bash"]
