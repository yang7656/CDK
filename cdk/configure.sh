#!/bin/bash
# use this to install software package for a web server
yum update -y
amazon-linux-extras install mariadb10.5
amazon-linux-extras install php8.2
yum install -y httpd
systemctl start httpd
systemctl enable httpd