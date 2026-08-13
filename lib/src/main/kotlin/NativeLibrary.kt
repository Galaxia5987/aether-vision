package com.galaxia5987

import org.bytedeco.javacpp.Loader
import org.bytedeco.javacpp.Pointer
import org.bytedeco.javacpp.annotation.Namespace
import org.bytedeco.javacpp.annotation.Platform

@Platform(
    include = ["NativeLibrary.h"],
    link = ["mylib"],
)
@Namespace("mylib")
class NativeLibrary : Pointer {
    companion object {
        init {
            Loader.load()
        }
    }

    constructor() {
        allocate()
    }

    // Binds to the C++ constructor to allocate memory
    private external fun allocate()

    // Binds to the C++ add function
    external fun add(
        a: Int,
        b: Int,
    ): Int
}
