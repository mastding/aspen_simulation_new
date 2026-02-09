"""
生成自签名SSL证书的工具脚本

使用方法:
    python generate_cert.py

生成的文件:
    - cert.pem: SSL证书文件
    - key.pem: 私钥文件
"""

from cryptography import x509
from cryptography.x509.oid import NameOID
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization
import datetime
import os


def generate_self_signed_cert(cert_file="cert.pem", key_file="key.pem"):
    """生成自签名SSL证书"""
    
    # 生成私钥
    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
    )
    
    # 创建证书主题
    subject = issuer = x509.Name([
        x509.NameAttribute(NameOID.COUNTRY_NAME, "CN"),
        x509.NameAttribute(NameOID.STATE_OR_PROVINCE_NAME, "Beijing"),
        x509.NameAttribute(NameOID.LOCALITY_NAME, "Beijing"),
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, "Aspen Simulation"),
        x509.NameAttribute(NameOID.COMMON_NAME, "localhost"),
    ])
    
    # 创建证书
    cert = x509.CertificateBuilder().subject_name(
        subject
    ).issuer_name(
        issuer
    ).public_key(
        private_key.public_key()
    ).serial_number(
        x509.random_serial_number()
    ).not_valid_before(
        datetime.datetime.utcnow()
    ).not_valid_after(
        datetime.datetime.utcnow() + datetime.timedelta(days=365)
    ).add_extension(
        x509.SubjectAlternativeName([
            x509.DNSName("localhost"),
            x509.DNSName("127.0.0.1"),
        ]),
        critical=False,
    ).sign(private_key, hashes.SHA256())
    
    # 写入证书文件
    with open(cert_file, "wb") as f:
        f.write(cert.public_bytes(serialization.Encoding.PEM))
    
    # 写入私钥文件
    with open(key_file, "wb") as f:
        f.write(private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.TraditionalOpenSSL,
            encryption_algorithm=serialization.NoEncryption()
        ))
    
    print(f"✓ 成功生成SSL证书:")
    print(f"  证书文件: {os.path.abspath(cert_file)}")
    print(f"  私钥文件: {os.path.abspath(key_file)}")
    print(f"  有效期: 365天")
    print(f"\n注意: 这是自签名证书，浏览器会显示安全警告，仅用于开发测试")


if __name__ == "__main__":
    generate_self_signed_cert()
