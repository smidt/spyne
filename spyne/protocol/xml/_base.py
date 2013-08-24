
#
# spyne - Copyright (C) Spyne contributors.
#
# This library is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 2.1 of the License, or (at your option) any later version.
#
# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public
# License along with this library; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301
#

"""The ``spyne.protocol.xml`` package contains an xml-based protocol that
serializes python objects to xml using Xml Schema conventions.

Logs valid documents to ``'%r'`` and invalid documents to ``'%r'``. Use the
usual ``logging.getLogger()`` and friends to configure how these get logged.

Warning! You can get a lot of crap in the 'invalid' logger. You're not advised
to turn it on for a production system.
""" % ('spyne.protocol.xml', 'spyne.protocol.xml.invalid')

import logging
logger = logging.getLogger('spyne.protocol.xml')
logger_invalid = logging.getLogger('spyne.protocol.xml.invalid')

from lxml import etree
from lxml.etree import XMLSyntaxError
from lxml.etree import XMLParser

from spyne import BODY_STYLE_WRAPPED

from spyne.util import _bytes_join

from spyne.const.ansi_color import LIGHT_GREEN
from spyne.const.ansi_color import LIGHT_RED
from spyne.const.ansi_color import END_COLOR

from spyne.util.cdict import cdict
from spyne.model import ModelBase
from spyne.model import Array
from spyne.model import Iterable
from spyne.model import XmlAttribute
from spyne.model import ComplexModelBase
from spyne.model import Fault
from spyne.model import ByteArray
from spyne.model import AnyHtml
from spyne.model import AnyXml
from spyne.model import AnyDict
from spyne.model import Unicode

from spyne.model.binary import Attachment # deprecated
from spyne.model.enum import EnumBase
from spyne.model.binary import BINARY_ENCODING_BASE64

from spyne.protocol import ProtocolBase

from spyne.protocol.xml.model import byte_array_to_parent_element
from spyne.protocol.xml.model import attachment_to_parent_element
from spyne.protocol.xml.model import base_to_parent_element
from spyne.protocol.xml.model import complex_to_parent_element
from spyne.protocol.xml.model import enum_to_parent_element
from spyne.protocol.xml.model import fault_to_parent_element
from spyne.protocol.xml.model import xml_to_parent_element
from spyne.protocol.xml.model import html_to_parent_element
from spyne.protocol.xml.model import dict_to_parent_element
from spyne.protocol.xml.model import xmlattribute_to_parent_element

from spyne.protocol.xml.model import attachment_from_element
from spyne.protocol.xml.model import base_from_element
from spyne.protocol.xml.model import byte_array_from_element
from spyne.protocol.xml.model import complex_from_element
from spyne.protocol.xml.model import enum_from_element
from spyne.protocol.xml.model import fault_from_element
from spyne.protocol.xml.model import xml_from_element
from spyne.protocol.xml.model import array_from_element
from spyne.protocol.xml.model import iterable_from_element
from spyne.protocol.xml.model import dict_from_element
from spyne.protocol.xml.model import unicode_from_element


class SchemaValidationError(Fault):
    """Raised when the input stream could not be validated by the Xml Schema."""

    def __init__(self, faultstring):
        Fault.__init__(self, 'Client.SchemaValidationError', faultstring)


class XmlDocument(ProtocolBase):
    """The Xml input and output protocol, using the information from the Xml
    Schema generated by Spyne types.

    See the following material for more (much much more!) information.

    * http://www.w3.org/TR/xmlschema-0/
    * http://www.w3.org/TR/xmlschema-1/
    * http://www.w3.org/TR/xmlschema-2/

    Receiving Xml from untrusted sources is a difficult dance in terms of
    security, as the Xml attack surface is huge.

    Spyne's ```lxml.etree.XMLParser``` instance has ```resolve_pis```,
    ```load_dtd```, ```resolve_entities```, ```dtd_validation```,
    ```huge_tree``` off by default.

    Having ```resolve_entities``` disabled will prevent the 'lxml' validation
    for documents with custom xml entities defined in the DTD. See the example
    in examples/xml/validation_error to play with the settings that work best
    for you. Please note that enabling ```resolve_entities``` is a security
    hazard that can lead to disclosure of sensitive information.

    See https://pypi.python.org/pypi/defusedxml for a pragmatic overview of
    Xml security in Python world.

    :param app: The owner application instance.
    :param validator: One of (None, 'soft', 'lxml', 'schema',
                ProtocolBase.SOFT_VALIDATION, XmlDocument.SCHEMA_VALIDATION).
                Both ``'lxml'`` and ``'schema'`` values are equivalent to
                ``XmlDocument.SCHEMA_VALIDATION``.
    :param xml_declaration: Whether to add xml_declaration to the responses
        Default is 'True'.
    :param cleanup_namespaces: Whether to add clean up namespace declarations
        in the response document. Default is 'True'.
    :param encoding: The suggested string encoding for the returned xml
        documents. The transport can override this.
    :param pretty_print: When ``True``, returns the document in a pretty-printed
        format.

    The following are parsed straight to the XMLParser() instance. Docs are
    plagiarized from the lxml documentation. Some of the defaults are different
    to make it safer by default.

    :param attribute_defaults: read the DTD (if referenced by the document) and
        add the default attributes from it. Off by default.
    :param dtd_validation: validate while parsing (if a DTD was referenced). Off
        by default.
    :param load_dtd: load and parse the DTD while parsing (no validation is
        performed). Off by default.
    :param no_network: prevent network access when looking up external
        documents. On by default.
    :param ns_clean: try to clean up redundant namespace declarations. Off by
        default. The note that this is for incoming documents. The
        ```cleanup_namespaces``` parameter is for output documents, which is
        that's on by default.
    :param recover: try hard to parse through broken Xml. Off by default.
    :param remove_blank_text: discard blank text nodes between tags, also known
        as ignorable whitespace. This is best used together with a DTD or schema
        (which tells data and noise apart), otherwise a heuristic will be
        applied. Off by default.
    :param remove_pis: discard processing instructions. On by default.
    :param strip_cdata: replace CDATA sections by normal text content. On by
        default.
    :param resolve_entities: replace entities by their text value. Off by
        default.
    :param huge_tree: disable security restrictions and support very deep trees
        and very long text content. (only affects libxml2 2.7+) Off by default.
    :param compact: use compact storage for short text content. On by default.
    """

    SCHEMA_VALIDATION = type("Schema", (object,), {})

    mime_type = 'text/xml'
    default_binary_encoding = BINARY_ENCODING_BASE64

    type = set(ProtocolBase.type)
    type.add('xml')

    def __init__(self, app=None, validator=None, xml_declaration=True,
                cleanup_namespaces=True, encoding=None, pretty_print=False,
                attribute_defaults=False,
                dtd_validation=False,
                load_dtd=False,
                no_network=True,
                ns_clean=False,
                recover=False,
                remove_blank_text=False,
                remove_pis=True,
                strip_cdata=True,
                resolve_entities=False,
                huge_tree=False,
                compact=True
            ):
        ProtocolBase.__init__(self, app, validator)
        self.xml_declaration = xml_declaration
        self.cleanup_namespaces = cleanup_namespaces
        if encoding is None:
            self.encoding = 'UTF-8'
        else:
            self.encoding = encoding

        self.pretty_print = pretty_print

        self.serialization_handlers = cdict({
            AnyXml: xml_to_parent_element,
            Fault: fault_to_parent_element,
            AnyDict: dict_to_parent_element,
            AnyHtml: html_to_parent_element,
            EnumBase: enum_to_parent_element,
            ModelBase: base_to_parent_element,
            ByteArray: byte_array_to_parent_element,
            Attachment: attachment_to_parent_element,
            XmlAttribute: xmlattribute_to_parent_element,
            ComplexModelBase: complex_to_parent_element,
        })

        self.deserialization_handlers = cdict({
            AnyXml: xml_from_element,
            Fault: fault_from_element,
            AnyDict: dict_from_element,
            EnumBase: enum_from_element,
            ModelBase: base_from_element,
            Unicode: unicode_from_element,
            ByteArray: byte_array_from_element,
            Attachment: attachment_from_element,
            ComplexModelBase: complex_from_element,

            Iterable: iterable_from_element,
            Array: array_from_element,
        })

        self.log_messages = (logger.level == logging.DEBUG)
        self.parser_kwargs = dict(
            attribute_defaults=attribute_defaults,
            dtd_validation=dtd_validation,
            load_dtd=load_dtd,
            no_network=no_network,
            ns_clean=ns_clean,
            recover=recover,
            remove_blank_text=remove_blank_text,
            remove_comments=True,
            remove_pis=remove_pis,
            strip_cdata=strip_cdata,
            resolve_entities=resolve_entities,
            huge_tree=huge_tree,
            compact=compact,
            encoding=encoding,
        )

    def set_validator(self, validator):
        if validator in ('lxml', 'schema') or \
                                    validator is self.SCHEMA_VALIDATION:
            self.validate_document = self.__validate_lxml
            self.validator = self.SCHEMA_VALIDATION

        elif validator == 'soft' or validator is self.SOFT_VALIDATION:
            self.validator = self.SOFT_VALIDATION

        elif validator is None:
            pass

        else:
            raise ValueError(validator)

        self.validation_schema = None

    def from_element(self, cls, element):
        handler = self.deserialization_handlers[cls]
        return handler(self, cls, element)

    def to_parent_element(self, cls, value, tns, parent_elt, *args, **kwargs):
        handler = self.serialization_handlers[cls]
        return handler(self, cls, value, tns, parent_elt, *args, **kwargs)

    def validate_body(self, ctx, message):
        """Sets ctx.method_request_string and calls :func:`generate_contexts`
        for validation."""

        assert message in (self.REQUEST, self.RESPONSE), message

        line_header = LIGHT_RED + "Error:" + END_COLOR
        try:
            self.validate_document(ctx.in_body_doc)
            if message is self.REQUEST:
                line_header = LIGHT_GREEN + "Method request string:" + END_COLOR
            else:
                line_header = LIGHT_RED + "Response:" + END_COLOR
        finally:
            if self.log_messages:
                logger.debug("%s %s" % (line_header, ctx.method_request_string))
                logger.debug(etree.tostring(ctx.in_document, pretty_print=True))

    def create_in_document(self, ctx, charset=None):
        """Uses the iterable of string fragments in ``ctx.in_string`` to set
        ``ctx.in_document``."""

        string = _bytes_join(ctx.in_string)
        try:
            try:
                ctx.in_document = etree.fromstring(string,
                                        parser=XMLParser(**self.parser_kwargs))

            except ValueError:
                logger.debug('ValueError: Deserializing from unicode strings '
                             'with encoding declaration is not supported by '
                             'lxml.')
                ctx.in_document = etree.fromstring(string.decode(charset),
                                                                    self.parser)
        except XMLSyntaxError, e:
            logger_invalid.error(string)
            raise Fault('Client.XMLSyntaxError', str(e))

    def decompose_incoming_envelope(self, ctx, message):
        assert message in (self.REQUEST, self.RESPONSE)

        ctx.in_header_doc = None # If you need header support, you should use Soap
        ctx.in_body_doc = ctx.in_document
        ctx.method_request_string = ctx.in_body_doc.tag
        self.validate_body(ctx, message)

    def create_out_string(self, ctx, charset=None):
        """Sets an iterable of string fragments to ctx.out_string"""

        if charset is None:
            charset = self.encoding

        ctx.out_string = [etree.tostring(ctx.out_document,
                                          encoding=charset,
                                          pretty_print=self.pretty_print,
                                          xml_declaration=self.xml_declaration)]

        if self.log_messages:
            logger.debug('%sResponse%s %s' % (LIGHT_RED, END_COLOR,
                            etree.tostring(ctx.out_document,
                                          pretty_print=True, encoding='UTF-8')))

    def deserialize(self, ctx, message):
        """Takes a MethodContext instance and a string containing ONE root xml
        tag.

        Returns the corresponding native python object

        Not meant to be overridden.
        """

        assert message in (self.REQUEST, self.RESPONSE)

        self.event_manager.fire_event('before_deserialize', ctx)

        if ctx.descriptor is None:
            if ctx.in_error is None:
                raise Fault("Client", "Method %r not found." %
                                                      ctx.method_request_string)
            else:
                raise ctx.in_error

        if message is self.REQUEST:
            body_class = ctx.descriptor.in_message
        elif message is self.RESPONSE:
            body_class = ctx.descriptor.out_message

        # decode method arguments
        if ctx.in_body_doc is None:
            ctx.in_object = [None] * len(body_class._type_info)
        else:
            ctx.in_object = self.from_element(body_class, ctx.in_body_doc)

        if self.log_messages and message is self.REQUEST:
            line_header = '%sRequest%s' % (LIGHT_GREEN, END_COLOR)

            logger.debug("%s %s" % (line_header, etree.tostring(ctx.out_document,
                    xml_declaration=self.xml_declaration, pretty_print=True)))

        self.event_manager.fire_event('after_deserialize', ctx)

    def serialize(self, ctx, message):
        """Uses ctx.out_object, ctx.out_header or ctx.out_error to set
        ctx.out_body_doc, ctx.out_header_doc and ctx.out_document as an
        lxml.etree._Element instance.

        Not meant to be overridden.
        """

        assert message in (self.REQUEST, self.RESPONSE)

        self.event_manager.fire_event('before_serialize', ctx)

        if ctx.out_error is not None:
            # FIXME: There's no way to alter soap response headers for the user.
            tmp_elt = etree.Element('punk')
            retval = self.to_parent_element(ctx.out_error.__class__, ctx.out_error,
                                    self.app.interface.get_tns(), tmp_elt)

            ctx.out_document = tmp_elt[0]

        else:
            if message is self.REQUEST:
                result_message_class = ctx.descriptor.in_message
            elif message is self.RESPONSE:
                result_message_class = ctx.descriptor.out_message

            # assign raw result to its wrapper, result_message
            if ctx.descriptor.body_style == BODY_STYLE_WRAPPED:
                result_message = result_message_class()

                for i, attr_name in enumerate(
                                        result_message_class._type_info.keys()):
                    setattr(result_message, attr_name, ctx.out_object[i])

            else:
                result_message = ctx.out_object

            # transform the results into an element
            tmp_elt = etree.Element('punk')
            retval = self.to_parent_element(result_message_class,
                        result_message, self.app.interface.get_tns(), tmp_elt)
            ctx.out_document = tmp_elt[0]

        if self.cleanup_namespaces:
            etree.cleanup_namespaces(ctx.out_document)

        self.event_manager.fire_event('after_serialize', ctx)

        return retval

    def set_app(self, value):
        ProtocolBase.set_app(self, value)

        self.validation_schema = None

        if value:
            from spyne.interface.xml_schema import XmlSchema

            xml_schema = XmlSchema(value.interface)
            xml_schema.build_validation_schema()

            self.validation_schema = xml_schema.validation_schema

    def __validate_lxml(self, payload):
        ret = self.validation_schema.validate(payload)

        logger.debug("Validated ? %s" % str(ret))
        if ret == False:
            raise SchemaValidationError(
                               str(self.validation_schema.error_log.last_error))
