from marshmallow import Schema, fields, validate, validates, ValidationError


class AddCartItemSchema(Schema):
    variant_id = fields.Int(required=True, strict=True)
    quantity = fields.Int(required=True, strict=True, validate=validate.Range(min=1, max=99))


class UpdateCartItemSchema(Schema):
    quantity = fields.Int(required=True, strict=True, validate=validate.Range(min=0, max=99))


class CheckoutSchema(Schema):
    shipping_address_id = fields.Int(load_default=None)
    billing_address_id = fields.Int(load_default=None)
    currency = fields.Str(load_default="USD", validate=validate.Length(equal=3))
