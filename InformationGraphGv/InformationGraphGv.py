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

#
# REQUIREMENTS
#
# * Dump as much information as possible for each person and event into
#   the node:
#     - Date and place of birth
#     - Date and cause of death
#     - All other events (Residences, Graduations, etc)
#     - Occupations
#     - Notes
#     - Date and place of marriage
#     - Possibly references to sources of information
# * Changing the date stringification to print a more human-friendly date.
#   Eg, "16th December, 1842"; "June quarter, 1912"; "about 1875"
# * Include edges for non-primary event participants, eg, Witness,
#   Minister, etc.
# * Add labels for non-standard child relationship edges, or modify style
#   in some way to indicate different types, eg, Adopted, Step child, etc.
# * Include a legend for edge and node types
# * Use a method similar to the FamilyLines plugin to specify a list of
#   people to start spidering over the database from.  Also include a list
#   of people not to spider beyond.  This will allow dumps of one side of
#   a family tree.
# * Have the ability to store profiles of spider settings.  Eg, "Mum's
#   family", "Dad's family", "Everyone".

#------------------------------------------------------------------------
#
# GRAMPS module
#
#------------------------------------------------------------------------
from gramps.gen.const import GRAMPS_LOCALE as glocale
_ = glocale.translation.gettext
from gramps.gen.lib import EventRoleType, EventType, Person, Date, ChildRefType, FamilyRelType
from gramps.gen.utils.file import (media_path_full, find_file)
from gramps.gui.thumbnails import get_thumbnail_path
from gramps.gen.plug.report import Report
from gramps.gen.plug.report import utils as ReportUtils
from gramps.gen.plug.report import MenuReportOptions
from gramps.gen.plug.report import CATEGORY_GRAPHVIZ
from gramps.gen.plug.menu import (BooleanOption, EnumeratedListOption, FilterOption,
                                  PersonOption, PersonListOption, ColorOption)
from gramps.gen.utils.location import get_main_location
from gramps.gui.utils import ProgressMeter

#------------------------------------------------------------------------
#
# Python module
#
#------------------------------------------------------------------------
import re
from gi.repository import Gtk

#------------------------------------------------------------------------
#
# Public Constants
#
#------------------------------------------------------------------------
OPTION_PREFIX = 'INFO'

#------------------------------------------------------------------------
#
# InformationGraphOptions - Fills out report dialog with options
#
#------------------------------------------------------------------------
class InformationGraphOptions(MenuReportOptions):
    """
    Custom options for InformationGraph report
    """

    def __init__(self, name, dbase):
        MenuReportOptions.__init__(self, name, dbase)
    
    def add_menu_options(self, menu):
        category = _('People')

        option = PersonListOption(_('Start from'))
        option.set_help(_('People to start searching from'))
        menu.add_option(category, OPTION_PREFIX + 'start_people', option)

        option = PersonListOption(_('Don\'t pass'))
        option.set_help(_('People not to go beyond in the search'))
        menu.add_option(category, OPTION_PREFIX + 'terminals', option)

#------------------------------------------------------------------------
# Date display functions
#------------------------------------------------------------------------
def display_day(day):
    return str(day)

def display_month(month):
    if month == 1:
        return _('Jan')
    elif month == 2:
        return _('Feb')
    elif month == 3:
        return _('Mar')
    elif month == 4:
        return _('Apr')
    elif month == 5:
        return _('May')
    elif month == 6:
        return _('Jun')
    elif month == 7:
        return _('Jul')
    elif month == 8:
        return _('Aug')
    elif month == 9:
        return _('Sep')
    elif month == 10:
        return _('Oct')
    elif month == 11:
        return _('Nov')
    elif month == 12:
        return _('Dec')

def display_date_value(day, month, year):
    display = ''
    
    if day != 0:
        display += display_day(day)
        
    if month != 0:
        if len(display) > 0:
            display += ' '
        display += display_month(month)
            
    if year != 0:
        if len(display) > 0:
            display += ' '
        display += str(year)

    return display

def date_is_quarter(modifier, start_date, stop_date):
    # non-quarter modifier
    if modifier not in [Date.MOD_RANGE,Date.MOD_SPAN]:
        return False
    
    # specific start day
    if start_date[0] != 0:
        return False
    
    # specific stop day
    if stop_date[0] != 0:
        return False
    
    # year not equal
    if start_date[2] != start_date[2]:
        return False
    
    # non-quarter month span
    if (start_date[1], stop_date[1]) not in [(1,3),(4,6),(7,9),(10,12)]:
        return False
    
    return True

def display_quarter(start_date, stop_date):
    quarter_tup = (start_date[1],stop_date[1])
    if quarter_tup == (1,3):
        display = _('March qtr.')
    elif quarter_tup == (4,6):
        display = _('June qtr.')
    elif quarter_tup == (7,9):
        display = _('September qtr.')
    elif quarter_tup == (10,12):
        display = _('December qtr.')
        
    return display + ', ' + str(start_date[2])

def display_modifier(modifier):
    if modifier == Date.MOD_BEFORE:
        return _('before')
    elif modifier == Date.MOD_AFTER:
        return _('after')
    elif modifier == Date.MOD_ABOUT:
        return _('about')
    elif modifier == Date.MOD_RANGE:
        return _('between')
    elif modifier == Date.MOD_SPAN:
        return _('from')

def display_date(date):
    if date.is_empty():
        return None
    
    if not date.get_valid():
        return date.get_text()
    
    modifier = date.get_modifier()
    
    if modifier == Date.MOD_TEXTONLY:
        return get.get_text()
    
    compound = date.is_compound()
    
    if compound:
        start_date = date.get_start_date()
        stop_date  = date.get_stop_date()
        
        if date_is_quarter(modifier, start_date, stop_date):
            return display_quarter(start_date, stop_date)

    display = ''
    
    if modifier != Date.MOD_NONE:
        display += display_modifier(modifier) + ' '
    
    if compound:
        display += display_date_value(start_date[0], start_date[1], start_date[2])
        if modifier == Date.MOD_RANGE:
            display += _(' and ')
        else:
            display += _(' to ')
        display += display_date_value(stop_date[0], stop_date[1], stop_date[2])
    else:
        display += display_date_value(date.get_day(), date.get_month(), date.get_year())
        
    return display

#------------------------------------------------------------------------
# Style functions
#------------------------------------------------------------------------
def role_get_edge_properties(role):
    """
    Get a dictionary of properties for edges for a particular role type
    """
    # (style, color, weight, label with role)
    if role == EventRoleType.CLERGY:
        props = ('dashed', 'darkorchid', 0.8, True)
    elif role == EventRoleType.CELEBRANT:
        props = ('dotted', 'grey', 0.1, True)
    elif role == EventRoleType.AIDE:
        props = ('dashed', 'khaki', 0.7, True)
    elif role == EventRoleType.WITNESS:
        props = ('dashed', 'tan', 0.5, True)
    elif role == EventRoleType.BRIDE:
        props = ('solid', 'deeppink', 1.0, False)
    elif role == EventRoleType.GROOM:
        props = ('solid', 'dodgerblue4', 1.0, False)
    elif role == EventRoleType.FAMILY:
        props = ('solid', None, 1.0, False)
    elif role == EventRoleType.CUSTOM:
        props = ('dashed', 'grey42', 0.5, True)
    else:
        return {}

    props_dict = {'style':props[0], 'color':props[1], 'weight':props[2]}
    if props[3]:
        props_dict['label'] = str(role)

    return props_dict

def child_ref_type_get_edge_properties(typ):
    # (style, weight, label with relation)
    props = (None, None, None)
    props_dict = {}
    
    if typ == ChildRefType.BIRTH:
        return props_dict
#        props = (None, None, False)
    elif typ == ChildRefType.ADOPTED:
        props = ('dotted', 0.89, True)
    elif typ == ChildRefType.STEPCHILD:
        props = ('dashed', 0.83, False)
    elif typ == ChildRefType.SPONSORED:
        props = ('dotted', 0.80, True)
    elif typ == ChildRefType.UNKNOWN:
        props = ('dotted', 0.95, True)
    elif typ == ChildRefType.CUSTOM:
        props = ('dashed', None, True)
    else:
        props = ('dotted', 0.7, True)

    if props[0]:
        props_dict['style'] = props[0]
    if props[1]:
        props_dict['weight'] = props[1]
    if props[2]:
        props_dict['label'] = str(typ)

    return props_dict

def child_ref_get_edge_properties(child_ref):
    """
    Get a dictionary of properties for displaying the edge representing
    a child's relationship to its parents
    """
    props = {}
    father_rel = child_ref.get_father_relation()
    mother_rel = child_ref.get_mother_relation()

    if father_rel == mother_rel:
        props.update(child_ref_type_get_edge_properties(father_rel))
    else:
        if father_rel == ChildRefType.BIRTH:
            props.update(child_ref_type_get_edge_properties(mother_rel))
            props['color'] = 'dodgerblue4'
            props['weight'] = 0.9
        elif mother_rel == ChildRefType.BIRTH:
            props.update(child_ref_type_get_edge_properties(father_rel))
            props['color'] = 'deeppink'
            props['weight'] = 0.9
        else:
            # *shrug* go with father's relationship 
            props.update(child_ref_type_get_edge_properties(father_rel))
            props['color'] = 'purple'
            props['label'] = 'Paternal: ' + str(father_rel) + ', maternal: ' + str(mother_rel)
    
    return props

def family_rel_get_edge_properties(parent_rel):
    """
    Get a dictionary of properties for displaying the edge representing
    a parent's relationship to another parent
    """
    # (style, colour, label)
    if parent_rel == FamilyRelType.MARRIED:
        props = ('solid', None, False)
    elif parent_rel == FamilyRelType.UNMARRIED:
        props = ('dotted', 'plum', False)
    elif parent_rel == FamilyRelType.CIVIL_UNION:
        props = ('solid', 'darkorange', False)
    elif parent_rel == FamilyRelType.UNKNOWN:
        props = ('dashed', None, False)
    elif parent_rel == FamilyRelType.CUSTOM:
        props = ('dashed', 'turquoise', True)
    
    props_dict = {}
    if props[0]:
        props_dict['style'] = props[0]
    if props[1]:
        props_dict['color'] = props[1]
    if props[2]:
        props_dict['label'] = str(parent_rel)

    return props_dict

def family_get_node_properties(family):
    props = family_rel_get_edge_properties(family.get_relationship())
    props['shape'] = 'octagon'
    if props.has_key('label'):
        del props['label']
    return props

def person_get_node_properties(person):
    gender = person.get_gender()

    # (shape, color, style)
    if gender == Person.MALE:
        props = ('box', 'dodgerblue4', '')
    elif gender == Person.FEMALE:
        props = ('box', 'deeppink', 'rounded')
    elif gender == Person.UNKNOWN:
        props = ('hexagon', 'darkgreen', '')

    return {'shape':props[0], 'color':props[1], 'style':props[2]}
        
#------------------------------------------------------------------------
#
# InformationGraphReport - Generates a dot file
#
#------------------------------------------------------------------------

def sanitise(str):
    def alpharepl(stri):
    	return re.sub('\w', 'o', stri.group(0))
    return re.sub('>[^<]+<', alpharepl, str)

class InformationGraphReport(Report):
    """
    Produce a graph of people by spidering over the database
    from a set of individuals, not spidering past people in another
    set of individuals.
    """

    def __init__(self, database, options):
        Report.__init__(self, database, options)
        
        self.__db = database
        
        # set (private) member variables from options class
        option_prefix_len = len(OPTION_PREFIX)
        for (name, value) in options.handler.options_dict.iteritems():
            if name.startswith(OPTION_PREFIX):
                var = name[option_prefix_len:]
                setattr(self, '_InformationGraphReport__' + var, value)
        
        # set up spidering structures
        self.__current_people   = self.resolve_person_ids(self.__start_people)
        self.__terminal_ids     = self.__terminals.split()
        self.__seen_people      = []
        self.__seen_families    = []

        # output storage
        self.__nodes            = [] # (id, props)
        self.__edges            = [] # (from_id, to_id, to_port, props)
        
    def resolve_person_ids(self, id_list):
        people = []
        
        for id in id_list.split():
            person = self.__db.get_person_from_gramps_id(id)
            people.append(person)
            
        return people

    def resolve_entity_handles(self, entity_type, handle_list):
        entities = []
        get_from_handle = getattr(self.__db, 'get_' + entity_type + '_from_handle')

        for handle in handle_list:
            entity = get_from_handle(handle)
            entities.append(entity)

        return entities

    def resolve_family_handles(self, family_handle_list):
        return self.resolve_entity_handles('family', family_handle_list)
    
    def begin_report(self): 
        self.__progress = ProgressMeter(_('Generating Information Graph'))
	self.__progress.set_pass(header=_('Creating graph'), mode=ProgressMeter.MODE_ACTIVITY)
        
        while len(self.__current_people) > 0:
            person = self.__current_people.pop()
            self.process_person(person)
        
        self.__progress.set_header(_('Generating output...'))
        self.__progress.close()
        self.__progress = None

    def entity_in_list(self, entity, list):
        entity_id = entity.get_gramps_id()
        if entity_id in [x.get_gramps_id() for x in list]:
            return True
        return False

    def person_has_been_seen(self, person_id):
        return person_id in self.__seen_people
    
    def family_has_been_seen(self, family_id):
        return family_id in self.__seen_families
    
    def person_is_terminal(self, person_id):
        return person_id in self.__terminal_ids

    def handle_get_person_references(self, entity_handle):
        people = []
        for (class_name, handle) in self.__db.find_backlink_handles(entity_handle):
            if class_name == 'Person':
                people.append(self.__db.get_person_from_handle(handle))
        return people
    
    def process_person(self, person):
        id = person.get_gramps_id()
        if self.person_has_been_seen(id):
            return
        self.__seen_people.append(id)
        
        name = person.get_primary_name().get_name()
        self.__progress.set_header(_('Processing person ') + name)
        
        terminal = self.person_is_terminal(id)
                
        self.add_person(person, terminal)
        self.__progress.step()

        if not terminal:
            self.process_family_handle_list(person.get_family_handle_list())
            self.__progress.step()
            
            self.process_family_handle_list(person.get_parent_family_handle_list())
            self.__progress.step()
            
            self.process_person_ref_list(person, person.get_person_ref_list())
            self.__progress.step()

            self.process_person_references(person)
            self.__progress.step()

    def person_get_person_references(self, person):
        return self.handle_get_person_references(person.get_handle())
        
    def process_person_references(self, person):
        other_people = self.person_get_person_references(person)
        for other_person in other_people:
            self.process_person(other_person)
        
    def tabulate_event(self, event, prefix=True):
        event_type = event.get_type()

        if prefix:
            label = str(event_type)
        else:
            label = ''

        date_added = False
        place_added = False
        
        date = event.get_date_object()
        date_label = None
        if date != None:
            date_label = display_date(date)
            if date_label != None and len(date_label) > 0:
                if prefix:
                    label += ': '
                label += date_label
                date_added = True
        
        place_handle = event.get_place_handle()
        if place_handle != None:
            place = self.__db.get_place_from_handle(place_handle)
            if place != None:
                place_label = place.get_title()
                if place_label != None:
                    if not date_added:
                        if prefix:
                            label += ': '
                    else:
                        label += ', '
                    label += place_label
                    placed_added = True

        desc = event.get_description()
        if desc != None and len(desc) > 0:
            if date_added or place_added:
                label += ' ('
            label += desc
            if date_added or place_added:
                label += ')'
        
        table_label =  '<TR><TD ALIGN="LEFT" BALIGN="LEFT" PORT="'
        table_label += event.get_gramps_id()
        table_label += '">'
        table_label += label
        table_label += '</TD></TR>'
        
        return table_label
        
    def tabulate_person_attributes(self, person):
        attributes = person.get_attribute_list()
        if attributes == None or len(attributes) < 1:
            return None
        
        label = '<TR><TD ALIGN="LEFT" BALIGN="LEFT">'
        for attribute in attributes:
            label += "%s: %s<BR/>" % (attribute.get_type(), attribute.get_value())
        label += '</TD></TR>'
        
        return label
        
    def tabulate_person_photo(self, person):
        mediaList = person.get_media_list()
        if len(mediaList) < 1:
            return

        media_handle = mediaList[0].get_reference_handle()
        media = self.database.get_object_from_handle(media_handle)
        mime_type = media.get_mime_type()
        if mime_type[0:5] != "image":
            return
        
        media_path = media.get_path()
        full_path = media_path_full(self.__db, media_path)
        thumb_path = get_thumbnail_path(full_path)
            
        thumb_path = find_file(thumb_path)
        if thumb_path == None or len(thumb_path) < 1:
            return
        
        return '<TR><TD><IMG SRC="' + thumb_path + '" /></TD></TR>'

    def tabulate_note(self, note):
        LINE_LEN = 40

        label = '* '
        text = note.get()
        while len(text) > 0:
            space_pos = text.find(' ', LINE_LEN)

            if space_pos > 0:
                line = text[0:space_pos]
                text = text[space_pos+1:]
            else:
                line = text[0:LINE_LEN]
                text = text[LINE_LEN:]
            
            
            label += line
            label += '<BR/>'

        return '<TR><TD ALIGN="LEFT" BALIGN="LEFT">' + label + '</TD></TR>'
            
    
    def tabulate_person_notes(self, person):
        note_handles = person.get_note_list()
        if len(note_handles) < 1:
            return None

        label = ''
        for note_handle in note_handles:
            note = self.__db.get_note_from_handle(note_handle)
            label += self.tabulate_note(note)

        return label
        
    def add_person(self, person, terminal):
        attr_label  = self.tabulate_person_attributes(person)
        photo_label = self.tabulate_person_photo(person)
        notes_label = self.tabulate_person_notes(person)
        
        sole_label = not (attr_label or notes_label)
        event_label = self.add_person_events(person, terminal, sole_label)
        
        label = '<TABLE BORDER="0" CELLPADDING="0" CELLSPACING="0">'
        label += '<TR><TD>' + person.get_primary_name().get_name() + '</TD></TR>'

        if photo_label:
            label += photo_label
            
        if attr_label:
            label += attr_label
            
        if event_label:
            label += event_label

        if notes_label:
            label += notes_label
        
        label += '</TABLE>'

        props = person_get_node_properties(person)

        props['label'] = label
	
        self.add_node(person.get_gramps_id(), props)

    def add_person_events(self, person, terminal, sole_label):
        event_refs = person.get_event_ref_list()
        label = ''
        sole_label = sole_label and len(event_refs) == 1
        event_added = False
        for event_ref in event_refs:
            event_label = self.add_person_event_ref(person, terminal, event_ref, sole_label)
            if event_label != None:
                label += event_label
                event_added = True
            self.__progress.step()

        if not event_added:
            return None
        
        return label

    def entity_find_event_role(self, entity, event):
        event_id = event.get_gramps_id()
        
        event_refs = entity.get_event_ref_list()
        for event_ref in event_refs:
            ref_event = self.__db.get_event_from_handle(event_ref.get_reference_handle())
            if ref_event.get_gramps_id() == event_id:
                return event_ref.get_role()
    
    def add_event_back_references(self, entity, event, set_port_pos=False, terminal=False):
        # No census events edges
        if event.get_type() == EventType.CENSUS:
            return

        if event.get_type() in [EventType.DEATH]:
            reversed = True
            if set_port_pos:
                port_pos = 'w'
        else:
            reversed = False
            if set_port_pos:
                port_pos = 'e'
        
        entity_id = entity.get_gramps_id()
        event_handle = event.get_handle()
        
        event_id = event.get_gramps_id()
        port = event_id
        if set_port_pos:
            port += ':' + port_pos
        
        for (back_class_name, back_handle) in self.__db.find_backlink_handles(event_handle):
            func = getattr(self.__db, 'get_' + back_class_name.lower() + '_from_handle')
            back_entity = func(back_handle)
            back_id = back_entity.get_gramps_id()
            
            if back_id == entity_id:
                continue
            
            back_event_role = self.entity_find_event_role(back_entity, event)
            props = role_get_edge_properties(back_event_role)

            
            self.add_edge(back_id, entity_id, port, props, reversed)

            if not terminal:
                if back_class_name == 'Family':
                    self.process_family(back_entity)
                elif back_class_name == 'Person' and not terminal:
                    self.process_person(back_entity)
        
    def add_person_event_ref(self, person, terminal, event_ref, sole_label):
        event_handle = event_ref.get_reference_handle()
        event = self.__db.get_event_from_handle(event_handle)
        
        if event_ref.get_role() != EventRoleType.PRIMARY:
            return None
        
        self.add_event_back_references(person, event, True, terminal)
        
        if sole_label and event.get_type() == EventType.BIRTH:
            prefix = False
        else:
            prefix = True

        return self.tabulate_event(event, prefix)
    
    def process_person_ref_list(self, person, person_refs):
        for person_ref in person_refs:
            self.process_person_ref(person, person_ref)
            self.__progress.step()
    
    def process_person_ref(self, person, person_ref):
        for (entity_type, handle) in person_ref.get_referenced_handles():
            if entity_type == 'Person':
                other_person = self.__db.get_person_from_handle(handle)
                self.process_person_ref_person(person, person_ref, other_person)

    def process_person_ref_person(self, person, person_ref, other_person):
        self.process_person(other_person)

        relation = person_ref.get_relation()
        props = {'style':'dotted', 'color':'darkseagreen', 'label':relation}
        self.add_edge(person.get_gramps_id(), other_person.get_gramps_id(), None, props)
        
    def process_family_handle_list(self, family_handle_list):
        for family in self.resolve_family_handles(family_handle_list):
            self.process_family(family)
            
    def process_family(self, family):
        id = family.get_gramps_id()
        if self.family_has_been_seen(id):
            return
        self.__seen_families.append(id)
        
        self.process_family_children(family)
        
        parent_rel = family.get_relationship()
        parent_edge_props = family_rel_get_edge_properties(parent_rel)

        self.add_family_parent(family, 'father', parent_edge_props)
        self.add_family_parent(family, 'mother', parent_edge_props)

        self.add_family(family)

    def add_family_parent(self, family, parent_type, edge_props):
        handle_func = getattr(family, 'get_' + parent_type + '_handle')
        parent_handle = handle_func()
        if parent_handle == None:
            return
        
        parent = self.__db.get_person_from_handle(parent_handle)
        if parent == None:
            return
        parent_id = parent.get_gramps_id()
        
        self.add_edge(parent_id, family.get_gramps_id(), None, edge_props)
        
        self.process_person(parent)
        
    def process_family_children(self, family):
        child_refs = family.get_child_ref_list()
        for child_ref in child_refs:
            self.add_family_child_ref(family, child_ref)
            self.__progress.step()
        
    def add_family_child_ref(self, family, child_ref):
        child_handle = child_ref.get_reference_handle()
        child = self.__db.get_person_from_handle(child_handle)

        child_id = child.get_gramps_id()
        props = child_ref_get_edge_properties(child_ref)
        self.add_edge(family.get_gramps_id(), child_id, None, props)

        self.process_person(child)

    def add_family_events(self, family):
        event_refs = family.get_event_ref_list()
        event_ref_count = len(event_refs)
        if event_ref_count < 1:
            return None
        
        single_event = event_ref_count == 1
        label = ''
        for event_ref in event_refs:
            event_label = self.add_family_event_ref(family, event_ref, single_event)
            if event_label != None:
                label += event_label
            self.__progress.step()

        return label

#    def family_event_get_people(self, event_handle):
#        return self.handle_get_person_references(event_handle)
        
    def add_family_event_ref(self, family, event_ref, single_event):
        event_handle = event_ref.get_reference_handle()
        event = self.__db.get_event_from_handle(event_handle)
        
        if event_ref.get_role() != EventRoleType.FAMILY:
            return None
        
        self.add_event_back_references(family, event)
        
        if single_event and event.get_type() == EventType.MARRIAGE:
            prefix = False
        else:
            prefix = True
        
        return self.tabulate_event(event, prefix)
        

#    def add_family_event_ref_people(self, person, event_handle):
#        event_people = self.family_event_get_people(event_handle)
#        person_id = person.get_gramps_id()
#        
#        for event_person in event_people:
#            print "Found person '" + event_person.get_primary_name().get_name() + "' referencing family event"
#            event_person_id = event_person.get_gramps_id()
#            if event_person_id != person_id:
#                self.__current_people.append(event_person)
        

    def add_family(self, family):
        props = family_get_node_properties(family)
        label = ''
        
        event_label = self.add_family_events(family)
        if event_label:
            label += '<TABLE BORDER="0" CELLPADDING="0" CELLSPACING="0">'
            label += event_label
            label += '</TABLE>'
            
        props['label'] = label
        
        self.add_node(family.get_gramps_id(), props)

    def write_properties(self, properties):
        if not properties:
            return
        
        self.doc.write(' [')
        for prop in properties.iteritems():
            if prop[1] != None:
                if prop[0] == 'label':
                    self.doc.write(' %s=<%s>' % prop)
                else:
                    self.doc.write(' %s="%s"' % prop)
        self.doc.write(' ]')

    def write_node(self, id, properties=None):
        self.doc.write('  %s' % (id))
        self.write_properties(properties)
        self.doc.write(';\n')
        
    def write_edge(self, from_id, to_id, properties, reversed):
        if reversed:
            properties['arrowhead'] = 'none'
            properties['arrowtail'] = 'normal'
            t = from_id
            from_id = to_id
            to_id = t
        
        self.doc.write('  %s -> %s' % (from_id, to_id))
        self.write_properties(properties)
        self.doc.write(';\n')

    def add_node(self, id, props):
        self.__nodes.append( (id, props) )

    def add_edge(self, from_id, to_id, to_port, props, reversed=False):
        self.__edges.append( (from_id, to_id, to_port, props, reversed) )
    
    def write_report(self):
        node_ids = []
        for (id, props) in self.__nodes:
            self.write_node(id, props)
            node_ids.append(id)
        
        for (from_id, to_id, to_port, props, reversed) in self.__edges:
            if from_id not in node_ids:
                continue
            if to_id not in node_ids:
                continue
            
            if to_port:
                to = to_id + ":" + to_port
            else:
                to = to_id
            self.write_edge(from_id, to, props, reversed)

