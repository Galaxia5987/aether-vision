package com.galaxia5987.lib

import org.bytedeco.javacpp.Loader
import org.bytedeco.javacpp.Pointer
import org.bytedeco.javacpp.annotation.*

@Platform(
    include = ["inference/YoloDetector.hpp"],
    link = ["aether-vision-lib"]
)
class YoloBindings {

    companion object {
        init {
            Loader.load(YoloBindings::class.java)
        }
    }

    @Name("BoundingBox")
    @Namespace("aethervision")
    class BoundingBox : Pointer {
        constructor() { allocate() }
        constructor(p: Pointer) : super(p)

        external fun allocate()

        @MemberGetter external fun x(): Int
        @MemberSetter external fun x(x: Int): BoundingBox

        @MemberGetter external fun y(): Int
        @MemberSetter external fun y(y: Int): BoundingBox

        @MemberGetter external fun width(): Int
        @MemberSetter external fun width(width: Int): BoundingBox

        @MemberGetter external fun height(): Int
        @MemberSetter external fun height(height: Int): BoundingBox
    }

    @Name("Detection")
    @Namespace("aethervision")
    class Detection : Pointer {
        constructor() { allocate() }
        constructor(p: Pointer) : super(p)

        external fun allocate()

        @ByRef @MemberGetter external fun box(): BoundingBox
        @MemberSetter external fun box(@ByRef box: BoundingBox): Detection

        @MemberGetter external fun confidence(): Float
        @MemberSetter external fun confidence(confidence: Float): Detection

        @MemberGetter external fun class_id(): Int
        @MemberSetter external fun class_id(class_id: Int): Detection
    }

    @Name("std::vector<aethervision::Detection>")
    class DetectionVector : Pointer {
        constructor() { allocate() }
        constructor(n: Long) { allocate(n) }
        constructor(p: Pointer) : super(p)

        external fun allocate()
        external fun allocate(n: Long)

        @Name("operator=")
        @ByRef external fun put(@ByRef x: DetectionVector): DetectionVector

        @Index(function = "at")
        @ByRef external fun get(i: Long): Detection

        external fun size(): Long
        external fun push_back(@ByRef value: Detection)
        external fun clear()
    }

    @Name("YoloDetector")
    @Namespace("aethervision")
    class YoloDetector : Pointer {
        // Binds to the C++ constructor: YoloDetector(const std::string& modelPath, bool useCUDA)
        constructor(modelPath: String, useCUDA: Boolean = false) {
            allocate(modelPath, useCUDA)
        }

        private external fun allocate(modelPath: String, useCUDA: Boolean)

        // Binds to: std::vector<Detection> detect(void* imagePtr, float confThreshold, float iouThreshold)
        // Note: Returning by value in C++ requires @ByVal in JavaCPP
        @ByVal
        external fun detect(
            imagePtr: Pointer,
            confThreshold: Float = 0.25f,
            iouThreshold: Float = 0.45f
        ): DetectionVector
    }
}