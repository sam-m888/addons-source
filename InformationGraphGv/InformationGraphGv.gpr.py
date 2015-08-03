#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2008, 2009 Robert Ham <rah@bash.sh>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.

# InformationGraph.py - Information dump graphviz report plugin for GRAMPS

plg = newplugin()
plg.id    = 'information_graph'
plg.name  = _("Information Graph")
plg.description =  _("Produces a relationship graph with highly detailed nodes using Graphviz.")
plg.version = '0.2'
plg.gramps_target_version = '5.0'
plg.status = UNSTABLE
plg.fname = 'InformationGraphGv.py'
plg.ptype = REPORT
plg.authors = ["Bob Ham"]
plg.authors_email = ["rah@bash.sh"]
plg.category = CATEGORY_GRAPHVIZ
plg.reportclass = 'InformationGraphReport'
plg.optionclass = 'InformationGraphOptions'
plg.report_modes = [REPORT_MODE_GUI, REPORT_MODE_CLI]
plg.require_active = False
