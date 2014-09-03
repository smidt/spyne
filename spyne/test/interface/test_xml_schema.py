#!/usr/bin/env python
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

import logging
import unittest

from pprint import pprint
from lxml import etree

from spyne import Application
from spyne import rpc
from spyne.const import xml_ns as ns
from spyne.model import ByteArray
from spyne.model import ComplexModel
from spyne.model import XmlAttribute
from spyne.model import XmlData
from spyne.model import AnyXml
from spyne.model import Integer
from spyne.model import Mandatory as M
from spyne.model import Unicode
from spyne.model import Uuid
from spyne.model import Boolean
from spyne.protocol.soap import Soap11
from spyne.protocol.xml import XmlDocument
from spyne.service import ServiceBase
from spyne.util.xml import get_schema_documents
from spyne.util.xml import parse_schema_element
from spyne.util.xml import parse_schema_string

from spyne.interface.xml_schema import XmlSchema


class TestXmlSchema(unittest.TestCase):
    def test_choice_tag(self):
        class SomeObject(ComplexModel):
            __namespace__ = "badass_ns"

            one = Integer(xml_choice_group="numbers")
            two = Integer(xml_choice_group="numbers")
            punk = Unicode

        class KickassService(ServiceBase):
            @rpc(_returns=SomeObject)
            def wooo(ctx):
                return SomeObject()

        Application([KickassService],
            tns='kickass.ns',
            in_protocol=Soap11(validator='lxml'),
            out_protocol=Soap11()
        )

        docs = get_schema_documents([SomeObject])
        doc = docs['tns']
        print(etree.tostring(doc, pretty_print=True))
        assert len(doc.xpath('/xs:schema/xs:complexType[@name="SomeObject"]'
                                   '/xs:sequence/xs:element[@name="punk"]',
            namespaces={'xs': ns.xsd})) > 0
        assert len(doc.xpath('/xs:schema/xs:complexType[@name="SomeObject"]'
                    '/xs:sequence/xs:choice/xs:element[@name="one"]',
            namespaces={'xs': ns.xsd})) > 0

    def test_customized_class_with_empty_subclass(self):
        class SummaryStatsOfDouble(ComplexModel):
            _type_info = [('Min', XmlAttribute(Integer, use='required')),
                          ('Max', XmlAttribute(Integer, use='required')),
                          ('Avg', XmlAttribute(Integer, use='required'))]

        class SummaryStats(SummaryStatsOfDouble):
            ''' this is an empty base class '''

        class Payload(ComplexModel):
            _type_info = [('Stat1', SummaryStats.customize(nillable=False)),
                          ('Stat2', SummaryStats),
                          ('Stat3', SummaryStats),
                          ('Dummy', Unicode)]

        class JackedUpService(ServiceBase):
            @rpc(_returns=Payload)
            def GetPayload(ctx):
                return Payload()

        Application([JackedUpService],
            tns='kickass.ns',
            in_protocol=Soap11(validator='lxml'),
            out_protocol=Soap11()
        )

        # if no exceptions while building the schema, no problem.
        # see: https://github.com/arskom/spyne/issues/226


    def test_namespaced_xml_attribute(self):
        class Release(ComplexModel):
            __namespace__ = "http://usefulinc.com/ns/doap#"

            _type_info = [
                ('about', XmlAttribute(Unicode,
                             ns="http://www.w3.org/1999/02/22-rdf-syntax-ns#")),
            ]

        class Project(ComplexModel):
            __namespace__ = "http://usefulinc.com/ns/doap#"

            _type_info = [
                ('about', XmlAttribute(Unicode,
                             ns="http://www.w3.org/1999/02/22-rdf-syntax-ns#")),
                ('release', Release.customize(max_occurs=float('inf'))),
            ]

        class RdfService(ServiceBase):
            @rpc(Unicode, Unicode, _returns=Project)
            def some_call(ctx, a, b):
                pass

        Application([RdfService],
            tns='spynepi',
            in_protocol=Soap11(validator='lxml'),
            out_protocol=Soap11()
        )

        # if no exceptions while building the schema, no problem.

    def test_customized_simple_type_in_xml_attribute(self):
        class Product(ComplexModel):
            __namespace__ = 'some_ns'

            id = XmlAttribute(Uuid)
            edition = Unicode
            edition_id = XmlAttribute(Uuid, attribute_of='edition')

        class SomeService(ServiceBase):
            @rpc(Product, _returns=Product)
            def echo_product(ctx, product):
                logging.info('edition_id: %r', product.edition_id)
                return product

        Application([SomeService], tns='some_ns',
            in_protocol=Soap11(validator='lxml'),
            out_protocol=Soap11()
        )

        # if no exceptions while building the schema, no problem.

    def test_binary_encodings(self):
        class Product(ComplexModel):
            __namespace__ = 'some_ns'

            hex = ByteArray(encoding='hex')
            base64_1 = ByteArray(encoding='base64')
            base64_2 = ByteArray

        class SomeService(ServiceBase):
            @rpc(Product, _returns=Product)
            def echo_product(ctx, product):
                logging.info('edition_id: %r', product.edition_id)
                return product

        app = Application([SomeService],
            tns='some_ns',
            in_protocol=Soap11(validator='lxml'),
            out_protocol=Soap11()
        )

        _ns = {'xs': ns.xsd}
        pref_xs = ns.const_prefmap[ns.xsd]
        xs = XmlSchema(app.interface)
        xs.build_interface_document()
        elt = xs.get_interface_document()['tns'].xpath(
                    '//xs:complexType[@name="Product"]',
                    namespaces=_ns)[0]

        assert elt.xpath('//xs:element[@name="base64_1"]/@type',
                            namespaces=_ns)[0] == '%s:base64Binary' % pref_xs
        assert elt.xpath('//xs:element[@name="base64_2"]/@type',
                            namespaces=_ns)[0] == '%s:base64Binary' % pref_xs
        assert elt.xpath('//xs:element[@name="hex"]/@type',
                            namespaces=_ns)[0] == '%s:hexBinary' % pref_xs

    def test_multilevel_customized_simple_type(self):
        class ExampleService(ServiceBase):
            __tns__ = 'http://xml.company.com/ns/example/'

            @rpc(M(Uuid), _returns=Unicode)
            def say_my_uuid(ctx, uuid):
                return 'Your UUID: %s' % uuid

        Application([ExampleService],
            tns='kickass.ns',
            in_protocol=Soap11(validator='lxml'),
            out_protocol=Soap11()
        )

        # if no exceptions while building the schema, no problem.
        # see: http://stackoverflow.com/questions/16042132/cannot-use-mandatory-uuid-or-other-pattern-related-must-be-type-as-rpc-argumen

    def test_any_tag(self):
        logging.basicConfig(level=logging.DEBUG)

        class SomeType(ComplexModel):
            __namespace__ = "zo"

            anything = AnyXml(schema_tag='{%s}any' % ns.xsd, namespace='##other',
                                                         process_contents='lax')

        docs = get_schema_documents([SomeType])
        print(etree.tostring(docs['tns'], pretty_print=True))
        any = docs['tns'].xpath('//xsd:any', namespaces={'xsd': ns.xsd})

        assert len(any) == 1
        assert any[0].attrib['namespace'] == '##other'
        assert any[0].attrib['processContents'] == 'lax'

    def test_any_tag_with_unwrapped_options(self):
        logging.basicConfig(level=logging.DEBUG)

        class Key_value_store(ComplexModel):
            __namespace__ = "ns_any"

            key = AnyXml.customize(max_occurs='unbounded')
            value = AnyXml(schema_tag='{%s}any' % ns.xsd, _wrapper=True)
            #value_without_wrapping = AnyXml(schema_tag='{%s}any' % ns.xsd, wrapped=False)

        docs = get_schema_documents([Key_value_store])
        #print(etree.tostring(docs['tns'], pretty_print=True))

        # tests for value
        any_xml_1 = etree.Element('value')
        any_xml_1.text = 'test_value'

        any_xml_2 = etree.Element('value')
        subvalue_xml_1 = etree.SubElement(any_xml_2, 'string')
        subvalue_xml_1.text = 'subvalue_xml_1'
        subvalue_xml_2 = etree.SubElement(any_xml_2, 'string')
        subvalue_xml_2.text = 'subvalue_xml_2'

        key_value_store_1 = Key_value_store(value=any_xml_1)
        key_value_store_2 = Key_value_store(value=any_xml_2)

        #print((etree.tostring(key_value_store_1.value, pretty_print=True)))
        assert key_value_store_1.value.tag == 'value'
        assert key_value_store_1.value.text == 'test_value'
        assert len(key_value_store_1.value) == 0

        #print((etree.tostring(key_value_store.value, pretty_print=True)))
        assert len(key_value_store_2.value) == 2
        assert key_value_store_2.value[0].tag == 'string'
        assert key_value_store_2.value[0].text == 'subvalue_xml_1'
        assert key_value_store_2.value[1].tag == 'string'
        assert key_value_store_2.value[1].text == 'subvalue_xml_2'

        element_1 = etree.Element('parent_1')
        XmlDocument().to_parent(None, Key_value_store, key_value_store_1, element_1, ns.xsd)
        print((etree.tostring(element_1, pretty_print=True)))
        element_2 = etree.Element('parent_2')
        XmlDocument().to_parent(None, Key_value_store, key_value_store_2, element_2, ns.xsd)
        print((etree.tostring(element_2, pretty_print=True)))

        # Should work with and without wrapping
        store_1 = element_1[0][0]
        print((etree.tostring(store_1, pretty_print=True)))
        assert store_1[0].tag == 'value'
        assert store_1[0].text == 'test_value'
        assert len(store_1[0]) == 0

        store_2 = element_2[0][0]
        assert len(store_2[0]) == 2
        assert store_2[0][0].tag == 'string'
        assert store_2[0][0].text == 'subvalue_xml_1'
        assert store_2[0][1].tag == 'string'
        assert store_2[0][1].text == 'subvalue_xml_2'


        # TODO: use value_without_wrapping + tests


        # tests for key
        any_xml = etree.Element('key')
        any_xml.text = 'test_key'
        key_value_store = Key_value_store(key=[any_xml])

        print((etree.tostring(key_value_store.key[0], pretty_print=True)))
        assert key_value_store.key[0].tag == 'key'
        assert key_value_store.key[0].text == 'test_key'
        assert len(key_value_store.key[0]) == 0

        element = etree.Element('parent')
        XmlDocument().to_parent(None, Key_value_store, key_value_store, element, ns.xsd)
        print((etree.tostring(element, pretty_print=True)))
        assert 0

    def _build_xml_data_test_schema(self, custom_root):
        tns = 'kickass.ns'

        class ProductEdition(ComplexModel):
            __namespace__ = tns
            id = XmlAttribute(Uuid)
            if custom_root:
                name = XmlData(Uuid)
            else:
                name = XmlData(Unicode)

        class Product(ComplexModel):
            __namespace__ = tns
            id = XmlAttribute(Uuid)
            edition = ProductEdition

        class ExampleService(ServiceBase):
            @rpc(Product, _returns=Product)
            def say_my_uuid(ctx, product):
                pass

        app = Application([ExampleService],
            tns='kickass.ns',
            in_protocol=Soap11(validator='lxml'),
            out_protocol=Soap11()
        )

        schema = XmlSchema(app.interface)
        schema.build_interface_document()
        schema.build_validation_schema()

        doc = schema.get_interface_document()['tns']
        print(etree.tostring(doc, pretty_print=True))
        return schema

    def test_xml_data_schema_doc(self):
        schema = self._build_xml_data_test_schema(custom_root=False)

        assert len(schema.get_interface_document()['tns'].xpath(
                '/xs:schema/xs:complexType[@name="ProductEdition"]'
                '/xs:simpleContent/xs:extension/xs:attribute[@name="id"]'
                ,namespaces={'xs': ns.xsd})) == 1

    def _test_xml_data_validation(self):
        schema = self._build_xml_data_test_schema(custom_root=False)

        assert schema.validation_schema.validate(etree.fromstring("""
            <Product id="00000000-0000-0000-0000-000000000000" xmlns="kickass.ns">
                <edition id="00000000-0000-0000-0000-000000000001">punk</edition>
            </Product>
        """)), schema.validation_schema.error_log.last_error

    def _test_xml_data_validation_custom_root(self):
        schema = self._build_xml_data_test_schema(custom_root=True)

        assert schema.validation_schema.validate(etree.fromstring("""
            <Product id="00000000-0000-0000-0000-000000000000" xmlns="kickass.ns">
                <edition id="00000000-0000-0000-0000-000000000001">
                    00000000-0000-0000-0000-000000000002
                </edition>
            </Product>
        """)), schema.validation_schema.error_log.last_error


    def test_subs(self):
        from lxml import etree
        from spyne.util.xml import get_schema_documents
        xpath = lambda o, x: o.xpath(x, namespaces={"xs": ns.xsd})

        m = {
            "s0": "aa",
            "s2": "cc",
            "s3": "dd",
        }

        class C(ComplexModel):
            __namespace__ = "aa"
            a = Integer
            b = Integer(sub_name="bb")
            c = Integer(sub_ns="cc")
            d = Integer(sub_ns="dd", sub_name="dd")

        elt = get_schema_documents([C], "aa")['tns']
        print(etree.tostring(elt, pretty_print=True))

        seq, = xpath(elt, "xs:complexType/xs:sequence")

        assert len(seq) == 4
        assert len(xpath(seq, 'xs:element[@name="a"]')) == 1
        assert len(xpath(seq, 'xs:element[@name="bb"]')) == 1

        # FIXME: this doesn't feel right.
        # check the spec to see whether it should it be prefixed.
        #
        #assert len(xpath(seq, 'xs:element[@name="{cc}c"]')) == 1
        #assert len(xpath(seq, 'xs:element[@name="{dd}dd"]')) == 1

    def test_mandatory(self):
        xpath = lambda o, x: o.xpath(x, namespaces={"xs": ns.xsd})

        class C(ComplexModel):
            __namespace__ = "aa"
            foo = XmlAttribute(M(Unicode))

        elt = get_schema_documents([C])['tns']
        print(etree.tostring(elt, pretty_print=True))
        foo, = xpath(elt, 'xs:complexType/xs:attribute[@name="foo"]')
        attrs = foo.attrib
        assert 'use' in attrs and attrs['use'] == 'required'


class TestParseOwnXmlSchema(unittest.TestCase):
    def test_simple(self):
        tns = 'some_ns'
        class SomeGuy(ComplexModel):
            __namespace__ = 'some_ns'

            id = Integer

        schema = get_schema_documents([SomeGuy], tns)['tns']
        print(etree.tostring(schema, pretty_print=True))

        objects = parse_schema_element(schema)
        pprint(objects[tns].types)

        NewGuy = objects[tns].types["SomeGuy"]
        assert NewGuy.get_type_name() == SomeGuy.get_type_name()
        assert NewGuy.get_namespace() == SomeGuy.get_namespace()
        assert dict(NewGuy._type_info) == dict(SomeGuy._type_info)

    def test_customized_unicode(self):
        tns = 'some_ns'
        class SomeGuy(ComplexModel):
            __namespace__ = tns
            name = Unicode(max_len=10, pattern="a", min_len=5, default="aa")

        schema = get_schema_documents([SomeGuy], tns)['tns']
        print(etree.tostring(schema, pretty_print=True))

        objects = parse_schema_element(schema)
        pprint(objects[tns].types)

        NewGuy = objects['some_ns'].types["SomeGuy"]
        assert NewGuy._type_info['name'].Attributes.max_len == 10
        assert NewGuy._type_info['name'].Attributes.min_len == 5
        assert NewGuy._type_info['name'].Attributes.pattern == "a"
        assert NewGuy._type_info['name'].Attributes.default == "aa"

    def test_boolean_default(self):
        tns = 'some_ns'
        class SomeGuy(ComplexModel):
            __namespace__ = tns
            bald = Boolean(default=True)

        schema = get_schema_documents([SomeGuy], tns)['tns']
        print(etree.tostring(schema, pretty_print=True))

        objects = parse_schema_element(schema)
        pprint(objects[tns].types)

        NewGuy = objects['some_ns'].types["SomeGuy"]
        assert NewGuy._type_info['bald'].Attributes.default == True

    def test_boolean_attribute_default(self):
        tns = 'some_ns'
        class SomeGuy(ComplexModel):
            __namespace__ = tns

            bald = XmlAttribute(Boolean(default=True))

        schema = get_schema_documents([SomeGuy], tns)['tns']
        print(etree.tostring(schema, pretty_print=True))

        objects = parse_schema_element(schema)
        pprint(objects[tns].types)

        NewGuy = objects['some_ns'].types["SomeGuy"]
        assert NewGuy._type_info['bald'].Attributes.default == True

    def test_attribute(self):
        tns = 'some_ns'
        class SomeGuy(ComplexModel):
            __namespace__ = tns

            name = XmlAttribute(Unicode)

        schema = get_schema_documents([SomeGuy], tns)['tns']
        print(etree.tostring(schema, pretty_print=True))

        objects = parse_schema_element(schema)
        pprint(objects[tns].types)

        NewGuy = objects['some_ns'].types["SomeGuy"]
        assert NewGuy._type_info['name'].type is Unicode

    def test_attribute_with_customized_type(self):
        tns = 'some_ns'
        class SomeGuy(ComplexModel):
            __namespace__ = tns

            name = XmlAttribute(Unicode(default="aa"))

        schema = get_schema_documents([SomeGuy], tns)['tns']
        print(etree.tostring(schema, pretty_print=True))

        objects = parse_schema_element(schema)
        pprint(objects[tns].types)

        NewGuy = objects['some_ns'].types["SomeGuy"]
        assert NewGuy._type_info['name'].type.__orig__ is Unicode
        assert NewGuy._type_info['name'].type.Attributes.default == "aa"

    def test_simple_type_explicit_customization(self):
        class Header(ComplexModel):
            test = Boolean(min_occurs=0, nillable=False)
            pw = Unicode.customize(min_occurs=0, nillable=False, min_len=6)

        class Params(ComplexModel):
            sendHeader = Header.customize(nillable=False, min_occurs=1)

        class DummyService(ServiceBase):
            @rpc(Params, _returns=Unicode)
            def loadServices(ctx, serviceParams):
                return '42'

        Application([DummyService],
            tns='dummy',
            name='DummyService',
            in_protocol=Soap11(validator='lxml'),
            out_protocol=Soap11()
        )
        # if instantiation doesn't fail, test is green.


class TestParseForeignXmlSchema(unittest.TestCase):
    def test_simple_content(self):
        tns = 'some_ns'

        schema = """<xsd:schema xmlns:xsd="http://www.w3.org/2001/XMLSchema"
            targetNamespace="some_ns"
            elementFormDefault="qualified" attributeFormDefault="unqualified">
    <xsd:complexType name="SomeGuy">
        <xsd:simpleContent>
            <xsd:extension base="xsd:string">
                <xsd:attribute name="attr" type="xsd:string" use="optional"/>
            </xsd:extension>
        </xsd:simpleContent>
    </xsd:complexType>
</xsd:schema>"""

        objects = parse_schema_string(schema)
        pprint(objects[tns].types)

        NewGuy = objects[tns].types['SomeGuy']
        ti = NewGuy._type_info
        pprint(dict(ti))
        assert issubclass(ti['_data'], XmlData)
        assert ti['_data'].type is Unicode

        assert issubclass(ti['attr'], XmlAttribute)
        assert ti['attr'].type is Unicode


if __name__ == '__main__':
    unittest.main()

